package jp.local.wabun;
import java.math.BigInteger;
import java.util.regex.*;

/** Ordinary Japanese numerals. No readings inferred for surrounding kanji. */
public final class JapaneseNumbers {
    private static final Pattern RUN=Pattern.compile("[〇零一二三四五六七八九十百千万億兆0-9]+");
    private JapaneseNumbers(){}
    public static String convert(String text){
        Matcher m=RUN.matcher(text);StringBuffer out=new StringBuffer();
        while(m.find())m.appendReplacement(out,Matcher.quoteReplacement(number(m.group())));
        m.appendTail(out);return out.toString();
    }
    private static String number(String original){
        String s=original.replace('零','0').replace('〇','0');
        for(int i=0;i<9;i++)s=s.replace("一二三四五六七八九".charAt(i),(char)('1'+i));
        if(s.matches("[0-9]+"))return s; // Preserve zeros in digit sequences.
        try{
            BigInteger total=BigInteger.ZERO;long last=Long.MAX_VALUE;int start=0;
            for(int i=0;i<s.length();i++){
                char c=s.charAt(i);long unit=c=='兆'?1000000000000L:c=='億'?100000000L:c=='万'?10000L:0;
                if(unit==0)continue;
                if(unit>=last)throw new IllegalArgumentException();
                String part=s.substring(start,i);BigInteger n=part.isEmpty()?BigInteger.ONE:section(part);
                total=total.add(n.multiply(BigInteger.valueOf(unit)));last=unit;start=i+1;
            }
            if(start<s.length())total=total.add(section(s.substring(start)));
            return total.toString();
        }catch(IllegalArgumentException ex){return original;} // Malformed units remain unsupported; never guess.
    }
    private static BigInteger section(String s){
        BigInteger total=BigInteger.ZERO;int last=10000,start=0;
        for(int i=0;i<s.length();i++){
            char c=s.charAt(i);int unit=c=='千'?1000:c=='百'?100:c=='十'?10:0;
            if(unit==0){if(c<'0'||c>'9')throw new IllegalArgumentException();continue;}
            if(unit>=last)throw new IllegalArgumentException();
            String digits=s.substring(start,i);BigInteger n=digits.isEmpty()?BigInteger.ONE:new BigInteger(digits);
            total=total.add(n.multiply(BigInteger.valueOf(unit)));last=unit;start=i+1;
        }
        if(start<s.length())total=total.add(new BigInteger(s.substring(start)));
        return total;
    }
}
