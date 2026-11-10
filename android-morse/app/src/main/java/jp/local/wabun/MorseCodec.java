package jp.local.wabun;

import java.text.Normalizer;
import java.util.*;

/** Platform-independent Wabun rules. No language model or guessed text. */
public final class MorseCodec {
    public static final Map<Character,String> TABLE = new LinkedHashMap<>();
    private static final Map<String,Character> REVERSE = new HashMap<>();
    static {
        String kana="イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセスン";
        String[] codes={".-",".-.-","-...","-.-.","-..",".","..-..","..-.","--.","....","-.--.",".---","-.-",".-..","--","-.","---","---.",".--.","--.-",".-.","...","-","..-",".-..-","..--",".-...","...-",".--","-..-","-.--","--..","----","-.---",".-.--","--.--","-.-.-","-.-..","-..--","-...-","..-.-","--.-.",".--..","--..-","-..-.",".---.","---.-",".-.-."};
        for(int i=0;i<kana.length();i++) TABLE.put(kana.charAt(i),codes[i]);
        String[] digits={"-----",".----","..---","...--","....-",".....","-....","--...","---..","----."};
        for(int i=0;i<10;i++)TABLE.put((char)('0'+i),digits[i]);
        TABLE.put('゛',"..");TABLE.put('゜',"..--.");TABLE.put('ー',".--.-");TABLE.put('、',".-.-.-");TABLE.put('」',".-.-..");TABLE.put('（',"-.--.-");TABLE.put('）',".-..-.");
        TABLE.forEach((k,v)->{if(REVERSE.put(v,k)!=null)throw new IllegalStateException("duplicate code");});
    }
    public static String editableText(String input){
        String s=Normalizer.normalize(JapaneseNumbers.convert(Normalizer.normalize(input.replace('゛','\u3099').replace('゜','\u309a'),Normalizer.Form.NFKC)),Normalizer.Form.NFD);
        StringBuilder out=new StringBuilder();String small="ァィゥェォッャュョヮヵヶ",large="アイウエオツヤユヨワカケ";
        for(int i=0;i<s.length();){
            int raw=s.codePointAt(i);i+=Character.charCount(raw);int c=raw;
            if(Character.isWhitespace(c)){out.appendCodePoint(raw);continue;}
            if(c>='ぁ'&&c<='ゖ')c+=0x60;
            if(c=='\u3099')c='゛';if(c=='\u309a')c='゜';if(c=='(')c='（';if(c==')')c='）';if(c=='。')c='」';
            int n=small.indexOf(c);if(n>=0)c=large.charAt(n);
            if(c<=Character.MAX_VALUE&&TABLE.containsKey((char)c))out.appendCodePoint(raw);else out.append('□');
        }
        return hiragana(out.toString());
    }
    public static String previewLabels(String input) {
        String s=Normalizer.normalize(editableText(input),Normalizer.Form.NFD);
        String small="ァィゥェォッャュョヮヵヶ",large="アイウエオツヤユヨワカケ";
        StringBuilder b=new StringBuilder();
        for(int i=0;i<s.length();i++){
            char c=s.charAt(i);
            if(Character.isWhitespace(c)){if(b.length()>0&&b.charAt(b.length()-1)!=' ')b.append(' ');continue;}
            if(c>='ぁ'&&c<='ゖ')c+=0x60;
            if(c=='\u3099')c='゛';if(c=='\u309a')c='゜';
            if(c=='(')c='（';if(c==')')c='）';
            int n=small.indexOf(c);if(n>=0)c=large.charAt(n);
            // Wabun paragraph mark; this conversion is always shown before sending.
            if(c=='。')c='」';
            b.append(c);
        }
        String text=b.toString().trim();
        return text;
    }
    public static String normalize(String input){
        String text=previewLabels(input).replace("□","").trim().replaceAll(" +"," ");
        if(text.isEmpty())throw new IllegalArgumentException("送信できる文字がありません。□以外の文字を入力してください。");
        if(text.replace(" ","").length()>300)throw new IllegalArgumentException("1回の送信は300符号以内にしてください。");
        return text;
    }
    public static String hiragana(String labels){
        StringBuilder b=new StringBuilder();
        for(char c:Normalizer.normalize(labels,Normalizer.Form.NFD).toCharArray()){
            if(c>='ァ'&&c<='ヶ')c-=0x60;
            b.append(c=='゛'?'\u3099':c=='゜'?'\u309a':c);
        }
        return Normalizer.normalize(b,Normalizer.Form.NFC);
    }
    public static final class Pulse {
        public final boolean on;public final int units;
        public Pulse(boolean on,int units){this.on=on;this.units=units;}
    }
    public static List<Pulse> encode(String normalized){
        List<Pulse> out=new ArrayList<>();
        out.add(new Pulse(false,7));
        for(int i=0;i<normalized.length();i++){
            char c=normalized.charAt(i);if(c==' ')continue;
            String code=TABLE.get(c);if(code==null)throw new IllegalArgumentException("未対応文字");
            for(int j=0;j<code.length();j++){
                out.add(new Pulse(true,code.charAt(j)=='.'?1:3));
                if(j+1<code.length())out.add(new Pulse(false,1));
            }
            out.add(new Pulse(false,i+1==normalized.length()||normalized.charAt(i+1)==' '?7:3));
        }
        return out;
    }
    public static final class Decoder {
        private final double unit;
        private final StringBuilder symbols=new StringBuilder(),labels=new StringBuilder();
        private boolean on=false,initialized=false,wordAdded=false;
        private double since=0,last=0;
        public int uncertain=0;
        public Decoder(double unitSeconds){if(unitSeconds<=0)throw new IllegalArgumentException();unit=unitSeconds;}
        public void accept(boolean state,double seconds){
            if(initialized&&seconds+1e-9<last)throw new IllegalArgumentException("time order");last=seconds;
            if(!initialized){initialized=true;since=seconds;on=state;return;}
            if(state!=on){
                double length=(seconds-since)/unit;
                if(on){
                    if(length>=.45&&length<=1.75)symbols.append('.');
                    else if(length>=2.25&&length<=4.0)symbols.append('-');
                    else {symbols.append('?');}
                }else if(length>=2){flush();if(length>=5&&!wordAdded&&labels.length()>0){labels.append(' ');wordAdded=true;}}
                on=state;since=seconds;if(on)wordAdded=false;
            }
            if(!on){double gap=(seconds-since)/unit;if(gap>=2)flush();if(gap>=5&&!wordAdded&&labels.length()>0){labels.append(' ');wordAdded=true;}}
        }
        private void flush(){
            if(symbols.length()==0)return;
            Character c=REVERSE.get(symbols.toString());
            if(c==null){labels.append('□');uncertain++;}else labels.append(c);
            symbols.setLength(0);
        }
        /** Finalization preserves an incomplete ON as unknown, rather than guessing. */
        public void finish(){if(on){symbols.append('?');on=false;}flush();}
        public String text(){return hiragana(labels.toString()).trim();}
        public String pending(){return symbols.toString();}
        public void discontinuity(){symbols.setLength(0);labels.append('□');uncertain++;initialized=false;on=false;}
    }
    public static final class ToneDetector {
        private final int rate,n;private final double frequency,minimumRms;
        private final double[] samples;private int count=0;private long total=0;
        private boolean stable=false,candidate=false;private int streak=0;
        public double rms=0,ratio=0;
        public ToneDetector(int rate,double hz,double minimumRms){this.rate=rate;frequency=hz;this.minimumRms=minimumRms;n=Math.max(80,rate/100);samples=new double[n];}
        public void push(double sample,Decoder decoder){
            samples[count++]=sample;total++;
            if(count<n)return;count=0;
            double energy=0;for(double x:samples)energy+=x*x;rms=Math.sqrt(energy/n);
            double best=0;
            for(int offset=-25;offset<=25;offset+=25){
                double coeff=2*Math.cos(2*Math.PI*(frequency+offset)/rate),a=0,b=0;
                for(double x:samples){double v=x+coeff*a-b;b=a;a=v;}
                double power=a*a+b*b-coeff*a*b;best=Math.max(best,2*power/(n*Math.max(energy,1e-12)));
            }
            ratio=best;boolean detected=rms>=minimumRms&&ratio>=(stable?.30:.45);
            if(detected==candidate)streak++;else{candidate=detected;streak=1;}
            double time=(double)total/rate;
            if(candidate!=stable&&streak>=2){stable=candidate;decoder.accept(stable,time-(double)n/rate);}else decoder.accept(stable,time);
        }
    }
}
