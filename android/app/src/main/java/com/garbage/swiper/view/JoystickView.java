package com.garbage.swiper.view;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.MotionEvent;
import android.view.View;

public final class JoystickView extends View {
    public interface Listener {
        void onTilt(int x, int y);
        void onRelease();
    }

    private final Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint knob = new Paint(Paint.ANTI_ALIAS_FLAG);
    private Listener listener;
    private float cx, cy, radius, knobRadius, knobX, knobY;

    public JoystickView(Context context) {
        super(context);
        ring.setStyle(Paint.Style.STROKE);
        ring.setStrokeWidth(5f);
        ring.setColor(0xff78909c);
        knob.setStyle(Paint.Style.FILL);
        knob.setColor(0xff1976d2);
        setMinimumHeight(420);
    }

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    public void reset() {
        knobX = cx;
        knobY = cy;
        invalidate();
    }

    @Override protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
        cx = width / 2f;
        cy = height / 2f;
        radius = Math.min(width, height) * 0.40f;
        knobRadius = radius * 0.24f;
        reset();
    }

    @Override protected void onDraw(Canvas canvas) {
        canvas.drawCircle(cx, cy, radius, ring);
        canvas.drawCircle(knobX, knobY, knobRadius, knob);
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_MOVE:
                move(event.getX(), event.getY());
                return true;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                reset();
                if (listener != null) listener.onRelease();
                return true;
            default:
                return true;
        }
    }

    private void move(float x, float y) {
        float dx = x - cx;
        float dy = y - cy;
        float max = radius - knobRadius;
        float distance = (float) Math.sqrt(dx * dx + dy * dy);
        if (distance > max && distance > 0) {
            dx = dx / distance * max;
            dy = dy / distance * max;
        }
        knobX = cx + dx;
        knobY = cy + dy;
        invalidate();
        int tiltX = Math.round(dx / max * 100f);
        int tiltY = Math.round(-dy / max * 100f);
        if (listener != null) listener.onTilt(tiltX, tiltY);
    }
}
