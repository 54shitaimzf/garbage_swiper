package com.icar.app.view;

import android.content.Context;
import android.graphics.*;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

/**
 * 自定义摇杆控件 Canvas绘制圆形底座+手指, 坐标映射[-100,100]
 * 支持: 双击急停, 长按检测, 边缘防误触
 */
public class RockerView extends View {
    private Paint bgPaint, fingerPaint, glowPaint;

    // 圆心+手指位置
    private float cx, cy, fx, fy, radius, fingerRadius;
    private boolean fingerDown = false;

    // 回调
    private RockerListener rockerListener;
    public interface RockerListener {
        void onTilt(int tiltX, int tiltY);
        void onDoubleTap();
        void onLongPress();
        void onRelease();
    }
    public void setRockerListener(RockerListener l) { this.rockerListener = l; }

    // 双击检测
    private long lastDownTime = 0;
    private static final long DOUBLE_TAP_INTERVAL = 500;

    // 长按检测
    private Runnable longPressRunnable;
    private boolean isLongPress = false;
    private static final long LONG_PRESS_DELAY = 1000;

    // 边缘防误触阈值
    private static final float EDGE_THRESHOLD = 10f;

    // 激活态 (有触摸时放大+光晕)
    private boolean active = false;

    public RockerView(Context ctx, AttributeSet attrs) {
        super(ctx, attrs);
        init();
    }

    private void init() {
        bgPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        bgPaint.setStyle(Paint.Style.STROKE);
        bgPaint.setStrokeWidth(3f);
        bgPaint.setColor(0xFF999999);

        fingerPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        fingerPaint.setStyle(Paint.Style.FILL);
        fingerPaint.setColor(0xFFec761d);

        glowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        glowPaint.setStyle(Paint.Style.FILL);
        glowPaint.setColor(0x40ec761d);

        longPressRunnable = () -> {
            isLongPress = true;
            if (rockerListener != null) rockerListener.onLongPress();
        };
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        cx = w / 2f; cy = h / 2f;
        radius = Math.min(w, h) / 2f - 10f;
        fingerRadius = radius * 0.25f;
        if (!fingerDown) { fx = cx; fy = cy; }
        active = false;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        float r = active ? radius * 1.05f : radius;

        // 激活态光晕
        if (active) {
            canvas.drawCircle(cx, cy, r + 15f, glowPaint);
        }

        // 底座圆环
        canvas.drawCircle(cx, cy, r, bgPaint);

        // 手指圆
        float fr = active ? fingerRadius * 1.2f : fingerRadius;
        canvas.drawCircle(fx, fy, fr, fingerPaint);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        float tx = event.getX(), ty = event.getY();

        // 边缘防误触
        if (event.getAction() == MotionEvent.ACTION_DOWN &&
                (tx < EDGE_THRESHOLD || tx > getWidth() - EDGE_THRESHOLD ||
                 ty < EDGE_THRESHOLD || ty > getHeight() - EDGE_THRESHOLD)) {
            return false;
        }

        switch (event.getAction()) {
            case MotionEvent.ACTION_DOWN:
                fingerDown = true;
                active = true;
                isLongPress = false;

                // 双击检测
                long now = System.currentTimeMillis();
                if (now - lastDownTime < DOUBLE_TAP_INTERVAL) {
                    if (rockerListener != null) rockerListener.onDoubleTap();
                }
                lastDownTime = now;

                // 启动长按检测
                postDelayed(longPressRunnable, LONG_PRESS_DELAY);

                updateFinger(tx, ty);
                break;

            case MotionEvent.ACTION_MOVE:
                updateFinger(tx, ty);
                break;

            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                fingerDown = false;
                active = false;
                removeCallbacks(longPressRunnable);

                // 长按不重置, 普通松开才重置
                if (!isLongPress) {
                    fx = cx; fy = cy;
                    invalidate();
                    if (rockerListener != null) {
                        rockerListener.onTilt(0, 0);
                        rockerListener.onRelease();
                    }
                }
                isLongPress = false;
                break;
        }
        return true;
    }

    private void updateFinger(float tx, float ty) {
        // 限制在圆内
        float dx = tx - cx, dy = ty - cy;
        float dist = (float) Math.sqrt(dx * dx + dy * dy);
        if (dist > radius - fingerRadius) {
            tx = cx + dx / dist * (radius - fingerRadius);
            ty = cy + dy / dist * (radius - fingerRadius);
        }
        fx = tx; fy = ty;
        invalidate();

        // 坐标映射 [cx±r, cy±r] → [-100, 100]
        int tiltX = (int) ((fx - cx) / (radius - fingerRadius) * 100);
        int tiltY = (int) (-(fy - cy) / (radius - fingerRadius) * 100); // Y轴反转
        if (rockerListener != null) rockerListener.onTilt(tiltX, tiltY);
    }

    /** 外部调用: 重置摇杆到中心 */
    public void reset() {
        fx = cx; fy = cy;
        active = false;
        invalidate();
    }
}
