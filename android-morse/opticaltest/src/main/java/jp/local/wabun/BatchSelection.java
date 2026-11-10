package jp.local.wabun;

import java.util.LinkedHashSet;

/** A unique queue in the order checked; dialog edits are committed explicitly. */
public final class BatchSelection {
    private final LinkedHashSet<Integer> indices = new LinkedHashSet<>();
    public void add(int index) { if(index<0)throw new IllegalArgumentException(); indices.add(index); }
    public void remove(int index) { indices.remove(index); }
    public boolean contains(int index) { return indices.contains(index); }
    public void clear() { indices.clear(); }
    public BatchSelection copy() { BatchSelection copy=new BatchSelection();copy.indices.addAll(indices);return copy; }
    public void replace(BatchSelection other) { if(other==this)return;indices.clear();indices.addAll(other.indices); }
    public int[] indicesOr(int fallback) {
        if(indices.isEmpty())return new int[]{fallback};
        int[] result=new int[indices.size()];int i=0;
        for(int index:indices)result[i++]=index;
        return result;
    }
}
