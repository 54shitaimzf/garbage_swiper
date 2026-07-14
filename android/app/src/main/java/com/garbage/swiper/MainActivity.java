package com.garbage.swiper;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import com.garbage.swiper.protocol.CarDirection;
import com.garbage.swiper.protocol.CarEncode;
import com.garbage.swiper.tcp.CarTcpClient;
import com.garbage.swiper.view.JoystickView;

public final class MainActivity extends Activity {
    private final Handler main = new Handler(Looper.getMainLooper());
    private final CarTcpClient client = new CarTcpClient();
    private EditText hostInput;
    private EditText portInput;
    private TextView state;
    private SeekBar speedBar;
    private JoystickView joystick;
    private int rawX;
    private int rawY;
    private boolean joystickActive;
    private final Runnable repeatCommand = new Runnable() {
        @Override public void run() {
            if (joystickActive && client.isConnected()) {
                client.send(CarEncode.joystick(scale(rawX), scale(rawY)));
                main.postDelayed(this, 100);
            }
        }
    };

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        client.setListener(text -> runOnUiThread(() -> state.setText(text)));
        setContentView(buildUi());
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 18, 24, 18);
        root.setBackgroundColor(0xfff5f7fa);

        TextView title = label("园区巡检小车 · 官方控制", 22, Color.rgb(16, 24, 32));
        root.addView(title, params(-1, 58));

        LinearLayout address = new LinearLayout(this);
        hostInput = new EditText(this);
        hostInput.setSingleLine(true);
        hostInput.setText("10.71.253.19");
        hostInput.setHint("Jetson IP");
        address.addView(hostInput, weightParams(1));
        portInput = new EditText(this);
        portInput.setSingleLine(true);
        portInput.setInputType(2);
        portInput.setText("6000");
        address.addView(portInput, params(150, -2));
        Button connect = button("连接");
        address.addView(connect, params(150, -2));
        root.addView(address, params(-1, 62));

        state = label("未连接（车轮悬空测试）", 15, 0xff455a64);
        root.addView(state, params(-1, 42));
        connect.setOnClickListener(v -> connect());

        speedBar = new SeekBar(this);
        speedBar.setMax(40);
        speedBar.setProgress(12);
        root.addView(speedBar, params(-1, 50));
        TextView speed = label("限速 30%（首次测试建议保持低速）", 14, 0xff455a64);
        root.addView(speed, params(-1, 34));
        speedBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar b, int value, boolean fromUser) {
                int percent = Math.max(5, Math.round(value / 40f * 100f));
                speed.setText("限速 " + percent + "%（首次测试建议保持低速）");
            }
            @Override public void onStartTrackingTouch(SeekBar b) {}
            @Override public void onStopTrackingTouch(SeekBar b) {
                int p = Math.max(5, Math.round(b.getProgress() / 40f * 100f));
                client.send(CarEncode.setSpeed(p, p));
            }
        });

        joystick = new JoystickView(this);
        joystick.setListener(new JoystickView.Listener() {
            @Override public void onTilt(int x, int y) {
                rawX = x;
                rawY = y;
                joystickActive = true;
                client.send(CarEncode.joystick(scale(x), scale(y)));
                main.removeCallbacks(repeatCommand);
                main.postDelayed(repeatCommand, 100);
            }
            @Override public void onRelease() { stopCar(); }
        });
        root.addView(joystick, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout controls = new LinearLayout(this);
        controls.setGravity(Gravity.CENTER);
        addTouchButton(controls, "左移", CarDirection.LEFT);
        addTouchButton(controls, "前进", CarDirection.FRONT);
        addTouchButton(controls, "右移", CarDirection.RIGHT);
        addTouchButton(controls, "后退", CarDirection.BACK);
        Button stop = button("急停");
        stop.setTextColor(Color.WHITE);
        stop.setBackgroundColor(0xffc62828);
        stop.setOnClickListener(v -> stopCar());
        controls.addView(stop, params(150, 58));
        root.addView(controls, params(-1, 70));
        return root;
    }

    private void connect() {
        try {
            int port = Integer.parseInt(portInput.getText().toString().trim());
            client.connect(hostInput.getText().toString().trim(), port);
        } catch (NumberFormatException e) {
            Toast.makeText(this, "端口格式错误", Toast.LENGTH_SHORT).show();
        }
    }

    private void addTouchButton(LinearLayout row, String text, CarDirection direction) {
        Button button = button(text);
        button.setOnTouchListener((v, event) -> {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                client.send(CarEncode.direction(direction));
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_UP ||
                    event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                stopCar();
                return true;
            }
            return true;
        });
        row.addView(button, params(0, 58, 1));
    }

    private void stopCar() {
        joystickActive = false;
        main.removeCallbacks(repeatCommand);
        client.send(CarEncode.joystick(0, 0));
        client.send(CarEncode.direction(CarDirection.BRAKE));
        if (joystick != null) joystick.reset();
    }

    private int scale(int value) {
        int percent = Math.max(5, Math.round(speedBar.getProgress() / 40f * 100f));
        return Math.round(value * percent / 100f);
    }

    @Override protected void onPause() {
        stopCar();
        super.onPause();
    }

    @Override protected void onDestroy() {
        stopCar();
        client.close();
        super.onDestroy();
    }

    private TextView label(String text, int size, int color) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }

    private Button button(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextSize(13);
        return button;
    }

    private LinearLayout.LayoutParams params(int width, int height) {
        return new LinearLayout.LayoutParams(width, height);
    }

    private LinearLayout.LayoutParams params(int width, int height, float weight) {
        return new LinearLayout.LayoutParams(width, height, weight);
    }

    private LinearLayout.LayoutParams weightParams(float weight) {
        return params(0, -1, weight);
    }
}
