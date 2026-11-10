import jp.local.wabun.BatchSelection;
import jp.local.wabun.BatchRange;
import java.util.Arrays;

public class BatchSelectionTest {
    static void expect(BatchSelection q,int... expected) {
        if(!Arrays.equals(q.indicesOr(4),expected))throw new AssertionError();
    }
    public static void main(String[] args) {
        BatchSelection q=new BatchSelection();expect(q,4);
        q.add(2);q.add(0);q.add(1);q.add(2);expect(q,2,0,1);
        BatchSelection draft=q.copy();draft.remove(0);expect(q,2,0,1);
        draft.add(0);q.replace(draft);expect(q,2,1,0);
        int total=0;for(int i:q.indicesOr(4)){int[] r=BatchRange.full(i==0?"single65":"sentence",i==0?65:1);total+=r[1]-r[0]+1;}
        if(total!=67)throw new AssertionError("65 characters lost");
        q.clear();expect(q,4);
        System.out.println("BatchSelection: order, duplicate, cancel, reselect, fallback, 65 preservation OK");
    }
}
