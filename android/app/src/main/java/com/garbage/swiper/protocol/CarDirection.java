package com.garbage.swiper.protocol;

public enum CarDirection {
    STOP(0), FRONT(1), BACK(2), LEFT(3), RIGHT(4), LEFT_ROTATE(5), RIGHT_ROTATE(6), BRAKE(7);

    public final int value;

    CarDirection(int value) {
        this.value = value;
    }
}
