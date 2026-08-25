from ultralytics import YOLO

def train_emergency_model():
    # Load the base nano model (fastest)
    model = YOLO('yolov8n.pt')
    
    # Train the model on your custom dataset
    # You will need to create a dataset.yaml file that points to your images
    print("Starting training on Emergency Vehicles dataset...")
    results = model.train(
        data='emergency_dataset.yaml',  # Path to your dataset config file
        epochs=50,                      # Number of training epochs (increase if needed)
        imgsz=640,                      # Image size
        batch=16,                       # Batch size
        name='emergency_v1'             # Name of the training run
    )
    
    print("Training complete! Moving new weights to models/best.pt...")
    import shutil
    import os
    
    # Backup old weights just in case
    if os.path.exists('models/best.pt'):
        shutil.copy('models/best.pt', 'models/best_backup.pt')
        print("Backed up old weights to models/best_backup.pt")
        
    try:
        shutil.copy('runs/detect/emergency_v1/weights/best.pt', 'models/best.pt')
        print("✅ Successfully updated models/best.pt! The system will now use the new model.")
    except Exception as e:
        print(f"Error copying weights: {e}")
        print("Your new weights are saved in runs/detect/emergency_v1/weights/best.pt")

if __name__ == '__main__':
    train_emergency_model()
