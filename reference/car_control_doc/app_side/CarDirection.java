package com.icar.app.protocol;

/** 小车运动方向 */
public enum CarDirection {
    Stop(0), Front(1), After(2), Left(3), Right(4),
    LeftRotate(5), RightRotate(6), Brake(7);

    public final int value;
    CarDirection(int v) { this.value = v; }
}
