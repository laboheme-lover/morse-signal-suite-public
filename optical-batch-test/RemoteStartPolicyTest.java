import jp.local.wabun.RemoteStartPolicy;
import java.util.*;
public class RemoteStartPolicyTest {
    static String hash="a".repeat(64);
    static void reject(Runnable r){try{r.run();throw new AssertionError("invalid start accepted");}catch(IllegalArgumentException expected){}}
    public static void main(String[] args){
        Set<String> used=new HashSet<>();
        for(int speed:new int[]{300,450,600})RemoteStartPolicy.validate("fresh",used,false,hash,hash,speed,new int[]{64,0,1});
        reject(()->RemoteStartPolicy.validate("",used,false,hash,hash,300,new int[]{0}));
        reject(()->RemoteStartPolicy.validate("x",used,true,hash,hash,300,new int[]{0}));
        reject(()->RemoteStartPolicy.validate("x",used,false,hash,"b".repeat(64),300,new int[]{0}));
        reject(()->RemoteStartPolicy.validate("x",used,false,hash,hash,301,new int[]{0}));
        for(int[] ids:new int[][]{{},{-1},{65},{0,0}})reject(()->RemoteStartPolicy.validate("x",used,false,hash,hash,300,ids));
        used.add("done");reject(()->RemoteStartPolicy.validate("done",used,false,hash,hash,300,new int[]{0}));
        int[] all=new int[65];for(int i=0;i<65;i++)all[i]=i;
        RemoteStartPolicy.validate("all",used,false,hash,hash,600,all);
        System.out.println("Remote start policy: valid speeds/order/all65; duplicate/busy/hash/speed/range rejected PASS");
    }
}
