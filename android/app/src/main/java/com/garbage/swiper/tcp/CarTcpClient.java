package com.garbage.swiper.tcp;

import android.os.Handler;
import android.os.Looper;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Small, single-owner client for the official Rosmaster TCP service. */
public final class CarTcpClient {
    public interface Listener {
        void onState(String state);
    }

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private volatile Socket socket;
    private volatile OutputStream output;
    private volatile boolean connected;
    private Listener listener;

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    public boolean isConnected() {
        return connected;
    }

    public void connect(String host, int port) {
        disconnect();
        state("连接中 " + host + ":" + port);
        io.execute(() -> {
            try {
                Socket s = new Socket();
                s.connect(new InetSocketAddress(host, port), 3000);
                s.setTcpNoDelay(true);
                socket = s;
                output = s.getOutputStream();
                connected = true;
                state("已连接 " + host + ":" + port);
            } catch (IOException e) {
                connected = false;
                state("连接失败: " + e.getMessage());
            }
        });
    }

    public void send(String frame) {
        if (!connected || output == null) return;
        io.execute(() -> {
            try {
                output.write((frame + "\n").getBytes(StandardCharsets.US_ASCII));
                output.flush();
            } catch (IOException e) {
                connected = false;
                state("发送失败，已断开");
            }
        });
    }

    public void disconnect() {
        connected = false;
        try { if (output != null) output.close(); } catch (IOException ignored) {}
        try { if (socket != null) socket.close(); } catch (IOException ignored) {}
        output = null;
        socket = null;
    }

    public void close() {
        disconnect();
        io.shutdownNow();
    }

    private void state(String text) {
        main.post(() -> {
            if (listener != null) listener.onState(text);
        });
    }
}
