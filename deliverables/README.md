# 园区智能无人巡检环卫终端

> **课程项目交付材料**　|　代码、文档、测试与演示入口

项目以 Jetson 小车为边缘计算平台，围绕“手机控制—视觉识别—本地告警—ROS2 扩展”的主线组织交付内容。

## 交付目录

```text
deliverables/
├── Document/     需求、设计开发、测试、使用、部署、管理与演示材料
├── Program/      程序目录说明
├── PPT/          答辩 PPT 提交说明
├── Video/        演示视频提交说明
└── Evaluation/   组员评价提交表
```

## 建议阅读顺序

1. `Document/00_project_narrative.md`：项目定位和答辩主线
2. `Document/01_requirements_analysis.md`：基础需求与完成口径
3. `Document/02_development_report.md`：系统架构和实现方案
4. `Document/03_test_report.md`：测试证据和未完成项
5. `Document/08_demo_script.md`：5-10 分钟演示流程
6. `Document/09_delivery_manifest.md`：最终提交检查

## 状态口径

- **已实现/已验证**：代码或接口已存在，并有测试或实际使用依据。
- **接口/仿真就绪**：软件骨架或 mock 流程可运行，但尚未完成真车闭环验收。
- **待现场验证**：需要在匹配的 Jetson、ROS2、传感器或演示环境中完成。

材料优先突出已验证的 8081 手动控制、`best.engine` 识别、视频与告警链路；ROS2、SLAM/Nav2、融合和 MQTT 按真实进度说明，不把规划内容表述为已完成。
