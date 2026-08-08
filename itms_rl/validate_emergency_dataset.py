"""
Validate YOLO emergency dataset quality before training.

Checks:
- YAML exists and has required names
- class IDs map to emergency classes only
- image/label files exist
- label rows are valid YOLO format
- class IDs in labels are valid

Usage:
  python validate_emergency_dataset.py --data emergency_dataset.yaml
"""

import argparse
import glob
import os


def parse_args():
    p = argparse.ArgumentParser(description="Validate emergency YOLO dataset")
    p.add_argument("--data", required=True, help="Path to dataset YAML")
    return p.parse_args()


def parse_simple_yaml(path):
    data = {}
    names = {}
    in_names = False

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("names:"):
                in_names = True
                continue
            if in_names:
                if ":" in line and line[0].isdigit():
                    k, v = line.split(":", 1)
                    names[int(k.strip())] = v.strip().strip("'\"")
                    continue
                in_names = False
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip().strip("'\"")

    data["names"] = names
    return data


def resolve_path(base_dir, root_path, sub_path):
    if os.path.isabs(sub_path):
        return sub_path
    if root_path:
        root = root_path if os.path.isabs(root_path) else os.path.normpath(os.path.join(base_dir, root_path))
        return os.path.normpath(os.path.join(root, sub_path))
    return os.path.normpath(os.path.join(base_dir, sub_path))


def validate_label_file(label_path, max_class):
    issues = []
    with open(label_path, "r", encoding="utf-8") as f:
        for idx, raw in enumerate(f, start=1):
            row = raw.strip()
            if not row:
                continue
            parts = row.split()
            if len(parts) != 5:
                issues.append(f"{label_path}:{idx} invalid columns (expected 5)")
                continue
            try:
                cls = int(parts[0])
                x, y, w, h = map(float, parts[1:])
            except ValueError:
                issues.append(f"{label_path}:{idx} non-numeric label values")
                continue
            if cls < 0 or cls > max_class:
                issues.append(f"{label_path}:{idx} invalid class id {cls}")
            for v_name, v in (("x", x), ("y", y), ("w", w), ("h", h)):
                if not (0.0 <= v <= 1.0):
                    issues.append(f"{label_path}:{idx} {v_name} out of range [0,1]")
            if w <= 0 or h <= 0:
                issues.append(f"{label_path}:{idx} width/height must be > 0")
    return issues


def main():
    args = parse_args()
    yaml_path = args.data
    if not os.path.exists(yaml_path):
        raise SystemExit(f"Dataset YAML not found: {yaml_path}")

    cfg = parse_simple_yaml(yaml_path)
    names = cfg.get("names", {})

    required = {"ambulance", "police", "fire"}
    label_set = {str(v).strip().lower() for v in names.values()}
    if not required.issubset(label_set):
        print("WARNING: class names should include ambulance, police, fire for best accuracy")

    max_class = max(names.keys()) if names else -1
    if max_class < 0:
        raise SystemExit("No class names found in YAML under names:")

    base_dir = os.path.dirname(os.path.abspath(yaml_path))
    root_path = cfg.get("path", "")
    splits = [k for k in ("train", "val", "test") if k in cfg]
    if not splits:
        raise SystemExit("YAML must define at least train and val paths")

    total_images = 0
    total_labels = 0
    all_issues = []

    for split in splits:
        img_dir = resolve_path(base_dir, root_path, cfg[split])
        lbl_dir = img_dir.replace(f"{os.sep}images{os.sep}", f"{os.sep}labels{os.sep}")

        imgs = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp"):
            imgs.extend(glob.glob(os.path.join(img_dir, ext)))

        if not imgs:
            all_issues.append(f"{split}: no images found in {img_dir}")
            continue

        total_images += len(imgs)

        for img in imgs:
            stem = os.path.splitext(os.path.basename(img))[0]
            label_path = os.path.join(lbl_dir, stem + ".txt")
            if not os.path.exists(label_path):
                all_issues.append(f"missing label: {label_path}")
                continue
            total_labels += 1
            all_issues.extend(validate_label_file(label_path, max_class))

    print(f"Images checked: {total_images}")
    print(f"Label files checked: {total_labels}")
    print(f"Issue count: {len(all_issues)}")

    if all_issues:
        print("\nFirst 50 issues:")
        for item in all_issues[:50]:
            print("-", item)
        raise SystemExit("Dataset validation failed. Fix issues before training.")

    print("Dataset validation passed.")


if __name__ == "__main__":
    main()
