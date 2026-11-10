package jp.local.wabun;

/** Authoritative range: never depend on restored EditText or resume preferences. */
public final class BatchRange {
    private BatchRange() {}
    public static int[] full(String batchId, int count) {
        if ("single65".equals(batchId)) {
            if (count != 65) throw new IllegalArgumentException("単文字原稿が65ケースではありません。");
            return new int[]{1, 65};
        }
        if (count != 1) throw new IllegalArgumentException("単文バッチの原稿数が不正です。");
        return new int[]{1, 1};
    }
}
