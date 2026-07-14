package com.icar.app;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.icar.app.protocol.CarDirection;
import com.icar.app.protocol.CarEncode;
import com.icar.app.tcp.TCPClientManager;
import com.icar.app.view.RockerView;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** 遥控页: 按钮/摇杆切换 + 视频流 */
public class RemoteControlActivity extends AppCompatActivity {
    private TCPClientManager tcp;
    private RockerView rockerView;
    private View btnGrid;
    private WebView webView;
    private TextView tvVideoStatus;
    private String ip, videoPort;
    private boolean isRockerMode = false;
    private boolean isRecording = false;
    private Button btnRecord, btnPhoto;
    private Button btnLaserAvoid, btnLaserWarn, btnLaserStop;
    private Button btnSignDetect;
    private boolean signDetectActive = false;
    private SeekBar sbSpeed;
    private TextView tvSpeed;
    private int speedPercent = 40; // 当前速度百分比
    private String laserMode = null; // null, "avoidance", "tracking", "warning"
    private final ExecutorService httpExecutor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_remote_control);

        tcp = TCPClientManager.getInstance();
        ip = getIntent().getStringExtra("ip");
        videoPort = getIntent().getStringExtra("videoPort");

        rockerView = findViewById(R.id.rocker_view);
        btnGrid = findViewById(R.id.btn_grid);
        webView = findViewById(R.id.web_video);
        btnRecord = findViewById(R.id.btn_record);
        btnPhoto = findViewById(R.id.btn_photo);
        View btnRockerTab = findViewById(R.id.tab_rocker);
        View btnButtonTab = findViewById(R.id.tab_button);

        // 摇杆回调
        rockerView.setRockerListener(new RockerView.RockerListener() {
            @Override public void onTilt(int x, int y) {
                // 应用速度百分比缩放
                int sx = (int)(x * speedPercent / 100.0f);
                int sy = (int)(y * speedPercent / 100.0f);
                tcp.send(CarEncode.ctrlCar(sx, sy));
            }
            @Override public void onDoubleTap() {
                tcp.send(CarEncode.ctrlCar(0, 0));
                tcp.send(CarEncode.buttonCar(CarDirection.Brake));
                rockerView.reset();
            }
            @Override public void onLongPress() {}
            @Override public void onRelease() {
                tcp.send(CarEncode.buttonCar(CarDirection.Brake));
            }
        });

        // 方向按钮 (3x3 Grid)
        int[] btnIds = {R.id.btn_left_rotate, R.id.btn_forward, R.id.btn_right_rotate,
                        R.id.btn_left, R.id.btn_stop, R.id.btn_right,
                        0, R.id.btn_backward, 0};
        CarDirection[] dirs = {CarDirection.LeftRotate, CarDirection.Front, CarDirection.RightRotate,
                               CarDirection.Left, CarDirection.Brake, CarDirection.Right,
                               null, CarDirection.After, null};

        for (int i = 0; i < dirs.length; i++) {
            if (dirs[i] == null) continue;
            Button btn = findViewById(btnIds[i]);
            final CarDirection d = dirs[i];
            btn.setOnTouchListener((v, event) -> {
                switch (event.getAction()) {
                    case android.view.MotionEvent.ACTION_DOWN:
                        v.setPressed(true);
                        tcp.send(CarEncode.buttonCar(d));
                        break;
                    case android.view.MotionEvent.ACTION_UP:
                    case android.view.MotionEvent.ACTION_CANCEL:
                        v.setPressed(false);
                        tcp.send(CarEncode.buttonCar(CarDirection.Stop));
                        break;
                }
                return true;
            });
        }

        // Tab 切换
        btnRockerTab.setOnClickListener(v -> switchMode(true));
        btnButtonTab.setOnClickListener(v -> switchMode(false));
        switchMode(false); // 默认按钮模式

        // 视频 WebView
        tvVideoStatus = findViewById(R.id.tv_video_status);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                tvVideoStatus.setText(R.string.video_waiting);
                tvVideoStatus.setVisibility(View.VISIBLE);
                webView.setVisibility(View.GONE);
            }
            @Override
            public void onPageFinished(WebView view, String url) {
                tvVideoStatus.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
            }
            @Override
            public void onReceivedError(WebView view, android.webkit.WebResourceRequest req,
                                        android.webkit.WebResourceError err) {
                tvVideoStatus.setText(R.string.video_disconnected);
                tvVideoStatus.setVisibility(View.VISIBLE);
                webView.setVisibility(View.GONE);
            }
        });
        loadVideo();

        // 拍照
        btnPhoto.setOnClickListener(v -> tcp.send(CarEncode.takePhotos()));

        // 录像
        btnRecord.setOnClickListener(v -> {
            if (isRecording) {
                tcp.send(CarEncode.closeRecording());
                btnRecord.setText(R.string.btn_record_start);
            } else {
                tcp.send(CarEncode.startRecording());
                btnRecord.setText(R.string.btn_record_stop);
            }
            isRecording = !isRecording;
        });

        // 循迹
        CheckBox cbTrack = findViewById(R.id.cb_track);
        cbTrack.setOnCheckedChangeListener((btnView, checked) -> {
            tcp.send(checked ? CarEncode.trackingOpen() : CarEncode.trackingClose());
        });

        // 激光雷达模式按钮
        btnLaserAvoid = findViewById(R.id.btn_laser_avoidance);
        btnLaserWarn = findViewById(R.id.btn_laser_warning);
        btnLaserStop = findViewById(R.id.btn_laser_stop);

        // 速度控制滑块
        sbSpeed = findViewById(R.id.sb_speed);
        tvSpeed = findViewById(R.id.tv_speed);
        sbSpeed.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int v, boolean fromUser) {
                tvSpeed.setText(String.valueOf(v));
                speedPercent = v;
            }
            @Override public void onStartTrackingTouch(SeekBar s) {}
            @Override public void onStopTrackingTouch(SeekBar s) {
                tcp.send(CarEncode.setSpeed(s.getProgress(), s.getProgress()));
            }
        });
        // 初始化速度
        tcp.send(CarEncode.setSpeed(40, 40));

        btnLaserAvoid.setOnClickListener(v -> setLaserMode("avoidance"));
        btnLaserWarn.setOnClickListener(v -> setLaserMode("warning"));
        btnLaserStop.setOnClickListener(v -> setLaserMode(null));

        // 交通标志识别
        btnSignDetect = findViewById(R.id.btn_sign_detect);
        btnSignDetect.setOnClickListener(v -> toggleSignDetect());
    }

    private void switchMode(boolean rocker) {
        isRockerMode = rocker;
        rockerView.setVisibility(rocker ? View.VISIBLE : View.GONE);
        btnGrid.setVisibility(rocker ? View.GONE : View.VISIBLE);

        TextView tabRocker = findViewById(R.id.tab_rocker);
        TextView tabButton = findViewById(R.id.tab_button);

        int activeTextColor = getColor(R.color.tab_active_text);
        int inactiveTextColor = getColor(R.color.tab_inactive_text);
        if (rocker) {
            tabRocker.setBackgroundResource(R.drawable.bg_tab_active);
            tabRocker.setTextColor(activeTextColor);
            tabButton.setBackgroundResource(R.drawable.bg_tab_inactive);
            tabButton.setTextColor(inactiveTextColor);
        } else {
            tabButton.setBackgroundResource(R.drawable.bg_tab_active);
            tabButton.setTextColor(activeTextColor);
            tabRocker.setBackgroundResource(R.drawable.bg_tab_inactive);
            tabRocker.setTextColor(inactiveTextColor);
        }
    }

    /** 发送激光模式切换请求到小车 laser_server (端口8765) */
    private void setLaserMode(String mode) {
        String path = mode != null ? "/" + mode : "/stop";
        updateLaserButtons(mode);
        httpExecutor.execute(() -> {
            try {
                URL url = new URL("http://" + ip + ":8765" + path);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);
                int code = conn.getResponseCode();
                conn.disconnect();
                if (code == 200) {
                    laserMode = mode;
                    mainHandler.post(() -> updateLaserButtons(mode));
                } else {
                    mainHandler.post(() -> {
                        updateLaserButtons(laserMode); // revert
                        Toast.makeText(this, "激光服务错误: " + code, Toast.LENGTH_SHORT).show();
                    });
                }
            } catch (IOException e) {
                mainHandler.post(() -> {
                    updateLaserButtons(laserMode); // revert
                    Toast.makeText(this, "无法连接激光服务 :8765", Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    /** 高亮当前激活的激光按钮 */
    private void updateLaserButtons(String active) {
        int activeColor = getColor(R.color.accent);
        int normalColor = getColor(R.color.primary_light);
        btnLaserAvoid.setBackgroundColor("avoidance".equals(active) ? activeColor : normalColor);
        btnLaserWarn.setBackgroundColor("warning".equals(active) ? activeColor : normalColor);
    }

    /** 切换交通标志识别模式 */
    private void toggleSignDetect() {
        signDetectActive = !signDetectActive;
        String path = signDetectActive ? "/start" : "/stop";

        btnSignDetect.setEnabled(false);
        btnSignDetect.setText(signDetectActive ? R.string.sign_detect_stop : R.string.sign_detect_start);

        httpExecutor.execute(() -> {
            try {
                URL url = new URL("http://" + ip + ":8769" + path);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);
                int code = conn.getResponseCode();
                conn.disconnect();
                mainHandler.post(() -> {
                    btnSignDetect.setEnabled(true);
                    if (code == 200) {
                        if (signDetectActive) {
                            btnSignDetect.setText(R.string.sign_detect_stop);
                            btnSignDetect.setTextColor(getColor(R.color.danger));
                            Toast.makeText(this, "标志识别已开启", Toast.LENGTH_SHORT).show();
                        } else {
                            btnSignDetect.setText(R.string.sign_detect_start);
                            btnSignDetect.setTextColor(getColor(R.color.warning));
                            Toast.makeText(this, "标志识别已停止", Toast.LENGTH_SHORT).show();
                        }
                    } else {
                        signDetectActive = !signDetectActive; // revert
                        btnSignDetect.setText(R.string.sign_detect_start);
                        Toast.makeText(this, "标志识别服务错误: " + code, Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (IOException e) {
                mainHandler.post(() -> {
                    btnSignDetect.setEnabled(true);
                    signDetectActive = !signDetectActive; // revert
                    btnSignDetect.setText(R.string.sign_detect_start);
                    Toast.makeText(this, "无法连接标志识别服务 :8769", Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void loadVideo() {
        String url = "http://" + ip + ":" + videoPort + "/index2";
        webView.loadUrl(url);
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Release MJPEG connection when leaving page to prevent stale connections
        if (webView != null) {
            webView.stopLoading();
            webView.loadUrl("about:blank");
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null && webView.getUrl() != null && webView.getUrl().startsWith("about:")) {
            loadVideo();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        httpExecutor.shutdownNow();
        if (webView != null) {
            webView.stopLoading();
            webView.clearHistory();
            webView.loadUrl("about:blank");
            webView.destroy();
        }
    }
}
