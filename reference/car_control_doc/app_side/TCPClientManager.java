package com.icar.app.tcp;

import com.icar.app.protocol.CarEncode;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * TCP客户端管理器 (单例)
 */
public class TCPClientManager {
    private static TCPClientManager instance;
    private Socket socket;
    private OutputStream out;
    private BufferedReader in;
    private String ip = "172.20.10.3";
    private int port = 6001;
    private boolean connected = false;
    private ConnectionListener listener;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ExecutorService writeExecutor = Executors.newSingleThreadExecutor();

    public interface ConnectionListener {
        void onConnected();
        void onDisconnected();
        void onMessage(String message);
    }

    private TCPClientManager() {}

    public static synchronized TCPClientManager getInstance() {
        if (instance == null) instance = new TCPClientManager();
        return instance;
    }

    public void setAddress(String ip, int port) {
        this.ip = ip;
        this.port = port;
    }

    public void setListener(ConnectionListener l) { this.listener = l; }

    public boolean isConnected() { return connected; }

    public String getIp() { return ip; }
    public int getPort() { return port; }

    /** 异步连接 */
    public void connect(Runnable onResult) {
        executor.execute(() -> {
            try {
                disconnect(); // 先断开旧连接

                socket = new Socket();
                socket.connect(new InetSocketAddress(ip, port), 3000);
                out = socket.getOutputStream();
                in = new BufferedReader(new InputStreamReader(socket.getInputStream()));
                connected = true;

                if (listener != null) listener.onConnected();
                if (onResult != null) onResult.run();

                // 持续读取
                String line;
                while (connected && (line = in.readLine()) != null) {
                    if (listener != null) listener.onMessage(line);
                }
            } catch (IOException e) {
                connected = false;
                if (listener != null) listener.onDisconnected();
                if (onResult != null) onResult.run();
            }
        });
    }

    /** 发送消息 (异步, 避免 NetworkOnMainThreadException) */
    public void send(String message) {
        if (!connected || out == null) return;
        writeExecutor.execute(() -> {
            try {
                out.write((message + "\n").getBytes());
                out.flush();
            } catch (IOException e) {
                connected = false;
                if (listener != null) listener.onDisconnected();
            }
        });
    }

    /** 断开连接 */
    public void disconnect() {
        connected = false;
        try { if (in != null) in.close(); } catch (IOException ignored) {}
        try { if (out != null) out.close(); } catch (IOException ignored) {}
        try { if (socket != null) socket.close(); } catch (IOException ignored) {}
        socket = null; out = null; in = null;
    }
}
