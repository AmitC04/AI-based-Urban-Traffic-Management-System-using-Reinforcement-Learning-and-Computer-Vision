"""
Train a dedicated YOLO emergency-vehicle model (.pt) for:
- ambulance
- police
- fire

Usage (PowerShell):
  python train_emergency_model.py --data emergency_dataset.yaml --epochs 120 --imgsz 960

Output:
  models/emergency_best.pt
"""

import argparse
import os
import shutil

try:
    from ultralytics import YOLO
except ImportError as exc:
    raise SystemExit("ultralytics is required. Install with: pip install ultralytics") from exc


def parse_args():
    parser = argparse.ArgumentParser(description="Train emergency-only YOLO model")
    parser.add_argument("--data", required=True, help="Path to dataset YAML")
    parser.add_argument("--base", default="yolov8s.pt", help="Base model checkpoint")
    parser.add_argument("--epochs", type=int, default=120, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=960, help="Input image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--device", default="cpu", help="CUDA device id or cpu")
    parser.add_argument("--project", default="runs/emergency", help="YOLO project output dir")
    parser.add_argument("--name", default="train", help="YOLO run name")
    parser.add_argument("--patience", type=int, default=35, help="Early stop patience")
    return parser.parse_args()


def validate_dataset_yaml(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset YAML not found: {path}")


def export_best_pt(train_result):
    best = getattr(train_result, "best", None)
    if not best or not os.path.exists(str(best)):
        raise FileNotFoundError("YOLO training completed, but best.pt was not found.")

    os.makedirs("models", exist_ok=True)
    target = os.path.join("models", "emergency_best.pt")
    shutil.copy2(str(best), target)
    return target


def main():
    args = parse_args()
    validate_dataset_yaml(args.data)

    model = YOLO(args.base)
    result = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        patience=args.patience,
        optimizer="AdamW",
        lr0=0.0005,
        lrf=0.01,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5.0,
        translate=0.08,
        scale=0.20,
        fliplr=0.5,
        mosaic=0.5,
        mixup=0.10,
        close_mosaic=10,
        cache=True,
        amp=True,
        pretrained=True,
        verbose=True,
    )

    out = export_best_pt(result)
    print(f"Saved emergency model to: {out}")

    # Optional sanity validation on the produced checkpoint.
    best_model = YOLO(out)
    metrics = best_model.val(data=args.data, imgsz=args.imgsz, batch=max(1, args.batch // 2), device=args.device)
    print("Validation done. See YOLO logs for mAP metrics.")
    print(metrics)


if __name__ == "__main__":
    main()
