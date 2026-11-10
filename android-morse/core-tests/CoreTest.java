import jp.local.wabun.MorseCodec;
import jp.local.wabun.TextInput;
import jp.local.wabun.OpticalSignal;
import java.io.*;
import java.nio.charset.Charset;
import java.util.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;

public class CoreTest {
    static int tests=0;
    static void eq(Object a,Object b){tests++;if(!Objects.equals(a,b))throw new AssertionError("expected="+a+" actual="+b);}
    static void ok(boolean value){tests++;if(!value)throw new AssertionError("condition failed");}
    static String decodeCodes(String[] codes,double unit){
        MorseCodec.Decoder d=new MorseCodec.Decoder(unit);double t=0;d.accept(false,t);t+=7*unit;
        for(String code:codes){for(int j=0;j<code.length();j++){d.accept(true,t);t+=(code.charAt(j)=='.'?1:3)*unit;d.accept(false,t);t+=(j+1==code.length()?3:1)*unit;}}
        d.accept(false,t);d.finish();return d.text();
    }
    public static void main(String[] args)throws Exception{
        for(String line:Files.readAllLines(Path.of(args[0]),StandardCharsets.UTF_8)){String[] pair=line.split("\t");eq(pair[1],MorseCodec.TABLE.get(pair[0].charAt(0)));}
        eq(65,MorseCodec.TABLE.size());
        eq("がっこう （ぱん）",MorseCodec.hiragana("カ゛ッコウ （ハ゜ン）"));
        eq("カ゛ツコウ ハ゜ン」",MorseCodec.normalize("がっこう\nぱん。"));
        eq("（カ゛）",MorseCodec.normalize("(が)"));
        eq(MorseCodec.normalize("がっこう ぱん。"),MorseCodec.normalize("ｶﾞｯｺｳ パン。"));
        eq("がっこう ゔぁ",MorseCodec.hiragana("ガッコウ ヴァ"));
        for(String encoding:new String[]{"UTF-8","windows-31j","UTF-16"}){
            eq("がっこう\nぱん。",TextInput.read(new ByteArrayInputStream("ｶﾞｯｺｳ\r\nパン。".getBytes(Charset.forName(encoding)))));
        }
        eq("こんにちは",TextInput.read(new ByteArrayInputStream("\ufeffコンニチハ".getBytes(StandardCharsets.UTF_8))));
        eq("あ".repeat(300),TextInput.read(new ByteArrayInputStream("ア".repeat(300).getBytes(StandardCharsets.UTF_8))));
        for(String invalid:new String[]{""," \n","あ\u0000い"}){
            boolean rejected=false;try{TextInput.read(new ByteArrayInputStream(invalid.getBytes(StandardCharsets.UTF_8)));}catch(IllegalArgumentException e){rejected=true;}ok(rejected);
        }
        for(String editable:new String[]{"漢字","ABC","あ".repeat(301)})eq(MorseCodec.editableText(editable),TextInput.read(new ByteArrayInputStream(editable.getBytes(StandardCharsets.UTF_8))));
        eq("123 12 203 2026 10203 1000000000000 0010",MorseCodec.normalize("一二三 十二 二百三 二千二十六 一万二百三 一兆 〇零一〇"));
        eq("2おく3まん",MorseCodec.editableText("二おく三まん"));
        eq("200030000",MorseCodec.normalize("二億三万"));
        eq("12□あ□",MorseCodec.editableText("十二漢あ😀"));
        eq("12ア",MorseCodec.normalize("十二漢あ😀"));
        eq("アイ",MorseCodec.normalize("あ□漢字!い"));
        eq("ア イ",MorseCodec.normalize("あ □ い"));
        eq("□□",MorseCodec.editableText("十十"));
        eq("あ12□い",TextInput.read(new ByteArrayInputStream("ア十二漢イ".getBytes(StandardCharsets.UTF_8))));
        List<MorseCodec.Pulse> clean=MorseCodec.encode(MorseCodec.normalize("あい")),skipped=MorseCodec.encode(MorseCodec.normalize("あ□い"));
        eq(clean.size(),skipped.size());for(int i=0;i<clean.size();i++){eq(clean.get(i).on,skipped.get(i).on);eq(clean.get(i).units,skipped.get(i).units);}
        boolean tooLarge=false;try{TextInput.read(new ByteArrayInputStream(new byte[TextInput.MAX_BYTES+1]));}catch(IOException e){tooLarge=true;}ok(tooLarge);
        boolean malformed=false;try{TextInput.read(new ByteArrayInputStream(new byte[]{(byte)239,(byte)187,(byte)191,(byte)255}));}catch(IOException e){malformed=true;}ok(malformed);
        eq("は",decodeCodes(new String[]{"-..."},.12));
        eq("が",decodeCodes(new String[]{".-..",".."},.12));
        eq("ぱ",decodeCodes(new String[]{"-...","..--."},.3));
        eq("（あ）",decodeCodes(new String[]{"-.--.-","--.--",".-..-."},.12));
        eq("ー、」（）",decodeCodes(new String[]{".--.-",".-.-.-",".-.-..","-.--.-",".-..-."},.12));
        eq("ー、」（）",MorseCodec.normalize("ｰ､｡()"));
        eq("(こーひー、ぱん)」",TextInput.read(new ByteArrayInputStream("（コーヒー、パン）」".getBytes(StandardCharsets.UTF_8))));
        boolean failed=false;try{MorseCodec.normalize("漢字");}catch(IllegalArgumentException e){failed=true;}ok(failed);
        List<MorseCodec.Pulse> pulses=MorseCodec.encode("イ イ");
        eq(7,pulses.get(0).units);eq(1,pulses.get(2).units);eq(7,pulses.get(4).units);
        MorseCodec.Decoder words=new MorseCodec.Decoder(.1);words.accept(false,0);words.accept(true,.7);words.accept(false,.8);words.accept(true,1.5);words.accept(false,1.6);words.accept(false,2.3);eq("へ へ",words.text());
        MorseCodec.Decoder unknown=new MorseCodec.Decoder(.1);unknown.accept(true,0);unknown.accept(false,.2);unknown.accept(false,.6);eq("□",unknown.text());eq(1,unknown.uncertain);
        MorseCodec.Decoder truncated=new MorseCodec.Decoder(.1);truncated.accept(true,0);truncated.finish();eq("□",truncated.text());
        MorseCodec.Decoder gap=new MorseCodec.Decoder(.3);gap.accept(true,0);gap.discontinuity();gap.accept(false,4);eq("□",gap.text());
        String text="か゛つこう は゜ん（123）ー、」";String normalized=MorseCodec.normalize(text),expected=MorseCodec.hiragana(normalized);
        Random random=new Random(541);
        for(int rate:new int[]{8000,16000,44100})for(double unit:new double[]{.08,.12,.24})for(int frequency:new int[]{600,700,1000})for(double noise:new double[]{0,.01}){
            MorseCodec.Decoder d=new MorseCodec.Decoder(unit);MorseCodec.ToneDetector detector=new MorseCodec.ToneDetector(rate,frequency,.003);
            for(MorseCodec.Pulse pulse:MorseCodec.encode(normalized)){
                int n=(int)Math.round(pulse.units*unit*rate);
                for(int i=0;i<n;i++)detector.push((pulse.on?.2*Math.sin(2*Math.PI*frequency*i/rate):0)+noise*random.nextGaussian(),d);
            }
            d.finish();eq(expected,d.text());eq(0,d.uncertain);
        }
        MorseCodec.Decoder silence=new MorseCodec.Decoder(.12);MorseCodec.ToneDetector detector=new MorseCodec.ToneDetector(16000,700,.003);
        for(int i=0;i<16000*10;i++)detector.push(.01*random.nextGaussian(),silence);silence.finish();eq("",silence.text());
        // Simulated camera frames: 30 fps, random 4 ms timestamp jitter, fixed threshold states.
        MorseCodec.Decoder camera=new MorseCodec.Decoder(.3);double time=0;
        for(MorseCodec.Pulse pulse:MorseCodec.encode("カ゛ハ゜ン")){
            double end=time+pulse.units*.3;
            while(time<end){camera.accept(pulse.on,time);time+=1.0/30+(random.nextDouble()-.5)*.004;}
        }
        camera.finish();eq("がぱん",camera.text());
        for(String name:new String[]{"light_30fps.tsv","light_15fps.tsv"}){
            OpticalSignal video=new OpticalSignal(.6);
            for(String line:Files.readAllLines(Path.of(args[1],name),StandardCharsets.UTF_8)){
                String[] pair=line.split("\t");video.accept(Double.parseDouble(pair[1]),160,Double.parseDouble(pair[0]));
            }
            video.decoder.finish();eq("がら",video.decoder.text());eq(0,video.decoder.uncertain);
        }
        OpticalSignal lost=new OpticalSignal(.3);lost.accept(16,160,0);lost.accept(235,160,1);lost.decoder.finish();ok(lost.decoder.uncertain>0);
        boolean reversed=false;try{lost.accept(16,160,.5);}catch(IllegalArgumentException e){reversed=true;}ok(reversed);
        System.out.println("PASS "+tests+" assertions (including 54 synthetic audio scenarios; no physical-device accuracy claim)");
    }
}
