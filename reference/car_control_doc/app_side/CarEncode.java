package com.icar.app.protocol;

/**
 * 小车通信协议编码器
 * 格式: $ 01 TYPE SIZE DATA CHECKSUM #
 */
public final class CarEncode {
    private static final boolean DEBUG = true;
    private static final String TAG = "CarEncode";

    private CarEncode() {}

    /** 进入页面通知 */
    public static String enterPage(int page) {
        return baseEncode("0F", toHex(page, 2));
    }

    /** 查询硬件版本 */
    public static String getHardwareVersion() {
        return baseEncode("01");
    }

    /** 查询电池电压 */
    public static String getBattery() {
        return baseEncode("02");
    }

    /** 摇杆控制小车 speed_x/speed_y: -100~100 */
    public static String ctrlCar(int speedX, int speedY) {
        int sx = Math.round(speedX), sy = Math.round(speedY);
        if (sx < 0) sx += 256;
        if (sy < 0) sy += 256;
        if (DEBUG) android.util.Log.d(TAG, "ctrlCar: x=" + speedX + " y=" + speedY);
        return baseEncode("10", toHex(sx, 2) + toHex(sy, 2));
    }

    /** 按钮控制 */
    public static String buttonCar(CarDirection d) {
        return baseEncode("15", toHex(d.value, 2));
    }

    /** 四轮独立速度控制 L1/L2/R1/R2: -100~100 */
    public static String upSpeedCar(int l1, int l2, int r1, int r2) {
        return baseEncode("21",
                toHex(clamp(l1), 2) + toHex(clamp(l2), 2) +
                toHex(clamp(r1), 2) + toHex(clamp(r2), 2));
    }

    private static int clamp(int v) {
        v = Math.round(v);
        return v < 0 ? v + 256 : v;
    }

    /** 拍照 */
    public static String takePhotos() { return baseEncode("60"); }

    /** 开始录像 */
    public static String startRecording() { return baseEncode("61"); }

    /** 结束录像 */
    public static String closeRecording() { return baseEncode("62"); }

    /** 开始循迹 */
    public static String trackingOpen() { return baseEncode("63"); }

    /** 关闭循迹 */
    public static String trackingClose() { return baseEncode("64"); }

    /** 设置按钮控制速度 xy: 0~100 (前后左右), z: 0~100 (旋转) */
    public static String setSpeed(int xy, int z) {
        return baseEncode("16", toHex(Math.min(xy, 100), 2) + toHex(Math.min(z, 100), 2));
    }

    // === 内部方法 ===

    private static String baseEncode(String type, String... datas) {
        StringBuilder info = new StringBuilder();
        for (String s : datas) info.append(s);

        String size = toHex(info.length() + 2, 2);
        String code = "01" + type + size + info;
        code = code + toHex(checksum(code), 2);

        String result = "$" + code + "#";
        if (DEBUG) android.util.Log.d(TAG, "encode: " + result);
        return result;
    }

    static String toHex(int num, int len) {
        String hex = Integer.toHexString(num).toUpperCase();
        while (hex.length() < len) hex = "0" + hex;
        return hex;
    }

    static int checksum(String data) {
        int sum = 0;
        for (int i = 0; i < data.length(); i += 2)
            sum = (sum + Integer.parseInt(data.substring(i, i + 2), 16)) % 256;
        return sum;
    }
}
