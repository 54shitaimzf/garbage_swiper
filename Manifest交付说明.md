# 感知模型 manifest 交付说明（发给马展飞）

## 重要结论

1. **类别不能猜**：已从训练 `dataset/yolo/data.yaml` 固定为 5 类（见下方）。
2. **你现有的 `best.engine` / `yolo.engine` 很可能不含 EfficientNMS**（当时用 Ultralytics 默认导出）。组长只接受 `count/boxes/scores/classes` 结构 → **建议在小车上用 `nms=True` 重导一次**。
3. **完整 JSON 必须在 Jetson 上生成**（binding 名 + sha256 必须对着真实 engine 读）。

---

## 类别（可直接告诉组长）

```yaml
labels:
  - drink_white   # 0
  - drink_red     # 1
  - drink_green   # 2
  - backpack      # 3
  - tea_box       # 4
```

对应训练 data.yaml 的 names 顺序，**不要改成 foreign_object**。

---

## 小车上完整生成（复制执行）

### A. 把这两个脚本拷到小车 `~/icar_models/`

- `D:\北交大两周项目\icar_vision\scripts\generate_model_manifest.py`
- `D:\北交大两周项目\icar_vision\scripts\rebuild_engine_with_nms.sh`

```bash
mkdir -p ~/icar_models/validation
cp ~/Desktop/generate_model_manifest.py ~/icar_models/
cp ~/Desktop/rebuild_engine_with_nms.sh ~/icar_models/
chmod +x ~/icar_models/rebuild_engine_with_nms.sh
```

确认有 `best.pt`：

```bash
ls -lh ~/icar_models/best.pt
```

### B. 重导带 NMS 的 engine + 自动生成 JSON

```bash
cd ~/icar_models
bash rebuild_engine_with_nms.sh ~/icar_models
```

或分步：

```bash
cd ~/icar_models
pip3 install "numpy<1.24" ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple

python3 - <<'PY'
from ultralytics import YOLO
m = YOLO("best.pt")
print(m.export(format="engine", imgsz=640, half=True, device=0, nms=True))
PY

cp -f best.engine yolo.engine
python3 generate_model_manifest.py --engine best.engine --out model_manifest.json
sha256sum best.engine
cat model_manifest.json
```

成功标志：`model_manifest.json` 里 `outputs` 四个字段不是 `NEED_INSPECT` / `FIXME`。

### C. 准备验证图（组长要求）

```bash
mkdir -p ~/icar_models/validation
# 把一张已知有目标的图拷进去，改名为 foreign-object.jpg
cp ~/Desktop/你的测试图.jpg ~/icar_models/validation/foreign-object.jpg
sha256sum ~/icar_models/validation/foreign-object.jpg
```

再用画图/截图软件量出目标框 `[x1,y1,x2,y2]`，编辑 `model_manifest.json` 的：

```json
"validation": {
  "image_file": "validation/foreign-object.jpg",
  "image_sha256": "粘贴上面 sha256",
  "expected_class": "drink_red",
  "minimum_score": 0.5,
  "expected_box_xyxy": [真实的 x1, y1, x2, y2],
  "minimum_iou": 0.5
}
```

---

## 最终交付目录（给组长）

```text
~/icar_models/best.engine
~/icar_models/model_manifest.json
~/icar_models/validation/foreign-object.jpg
```

（`yolo.engine` 可作副本，主文件名按组长模板用 `best.engine`。）

---

## 先发给组长的文字（引擎重导完成前也可先发类别）

> 我训练 5 类，labels 顺序：  
> `["drink_white","drink_red","drink_green","backpack","tea_box"]`  
> 对应 data.yaml names。正在小车上用 `nms=True` 导出 EfficientNMS 引擎并生成完整 `model_manifest.json`（含 sha256 与真实 binding）。完成后放到 `~/icar_models/`。

---

## PC 上已备草稿

`icar_vision/models/model_manifest.json` —— **labels 已正确**；`engine_sha256` / `outputs` 仍需小车脚本补齐，**不要直接当最终交付件**。
