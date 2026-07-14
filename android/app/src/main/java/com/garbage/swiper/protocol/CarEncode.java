package com.garbage.swiper.protocol;

/** Official iCar ASCII-hex frame: $ 01 TYPE SIZE DATA CHECKSUM #. */
public final class CarEncode {
    private CarEncode() {}

    public static String joystick(int x, int y) {
        return frame("10", hex(signedByte(x)) + hex(signedByte(y)));
    }

    public static String direction(CarDirection direction) {
        return frame("15", hex(direction.value));
    }

    public static String setSpeed(int xy, int z) {
        return frame("16", hex(clamp(xy, 0, 100)) + hex(clamp(z, 0, 100)));
    }

    public static String battery() {
        return frame("02", "");
    }

    private static int signedByte(int value) {
        value = clamp(value, -100, 100);
        return value < 0 ? value + 256 : value;
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private static String hex(int value) {
        return String.format(java.util.Locale.US, "%02X", value & 0xFF);
    }

    private static String frame(String type, String data) {
        String body = "01" + type + hex(data.length() / 2 + 2) + data;
        int checksum = 0;
        for (int i = 0; i < body.length(); i += 2) {
            checksum = (checksum + Integer.parseInt(body.substring(i, i + 2), 16)) & 0xFF;
        }
        return "$" + body + hex(checksum) + "#";
    }
}
