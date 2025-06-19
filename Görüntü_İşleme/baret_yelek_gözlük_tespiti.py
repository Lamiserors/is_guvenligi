
# -*- coding: utf-8 -*-
"""
İş Güvenliği Baret Tespit Sistemi 
Roboflow veri setleri ile model eğitimi ve canlı kamera ile tespit

Gerekli paketler:
pip install ultralytics roboflow opencv-python pillow numpy requests pyyaml
"""

import cv2
import numpy as np
from ultralytics import YOLO
import datetime
import json
import sqlite3
import threading
import time
import os
import yaml
from roboflow import Roboflow
import requests
from PIL import Image
import shutil
import sqlite3


class HelmetDetectionTrainer:
    """Baret tespit modeli eğitim sınıfı """
    
    def __init__(self, project_name="helmet_detection"):
        self.project_name = project_name
        self.data_dir = f"datasets/{project_name}"
        self.model_dir = f"models/{project_name}"
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.model_dir, exist_ok=True)
        
    def download_roboflow_dataset(self, api_key, workspace, project, version=1):
        """Roboflow'dan veri seti indir"""
        try:
            print("Roboflow veri seti indiriliyor...")
            rf = Roboflow(api_key=api_key)
            project_obj = rf.workspace(workspace).project(project)
            dataset = project_obj.version(version).download("yolov8", location=self.data_dir)
            print(f"Veri seti başarıyla indirildi: {dataset.location}")
            return dataset.location
        
        except Exception as e:
            print(f"Roboflow veri seti indirme hatası: {e}")
            print("Manual olarak data.yaml yolunu kontrol edin...")
            return None
    
    def fix_data_yaml(self, dataset_path):
        """data.yaml dosyasını düzelt"""
        yaml_path = os.path.join(dataset_path, "data.yaml")
        
        if not os.path.exists(yaml_path):
            print(f" data.yaml bulunamadı: {yaml_path}")
            return None
            
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Yolları mutlak yollarla değiştir
            base_path = os.path.abspath(dataset_path)
            
            # Train ve val yollarını düzelt
            if 'train' in data:
                if not os.path.isabs(data['train']):
                    data['train'] = os.path.join(base_path, data['train']).replace('\\', '/')
                    
            if 'val' in data:
                if not os.path.isabs(data['val']):
                    data['val'] = os.path.join(base_path, data['val']).replace('\\', '/')
                    
            if 'test' in data:
                if not os.path.isabs(data['test']):
                    data['test'] = os.path.join(base_path, data['test']).replace('\\', '/')
            
            # Path'i düzelt
            data['path'] = base_path.replace('\\', '/')
            
            # Sınıf sayısını kontrol et
            if 'names' in data:
                data['nc'] = len(data['names'])
            
            # Düzeltilmiş yaml'ı kaydet
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                
            print(f"data.yaml düzeltildi: {yaml_path}")
            print(f"Sınıflar: {data.get('names', {})}")
            
            return yaml_path
            
        except Exception as e:
            print(f" data.yaml düzeltme hatası: {e}")
            return None
    
    def verify_dataset_structure(self, dataset_path):
        """Veri seti yapısını kontrol et"""
        required_dirs = ['train/images', 'train/labels', 'valid/images', 'valid/labels']
        
        print(f"\n Veri seti yapısı kontrol ediliyor: {dataset_path}")
        
        for dir_name in required_dirs:
            full_path = os.path.join(dataset_path, dir_name)
            if os.path.exists(full_path):
                file_count = len([f for f in os.listdir(full_path) 
                                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.txt'))])
                print(f" {dir_name}: {file_count} dosya")
            else:
                print(f" {dir_name}: Klasör bulunamadı")
                
        # data.yaml kontrolü
        yaml_path = os.path.join(dataset_path, "data.yaml")
        if os.path.exists(yaml_path):
            print(f" data.yaml mevcut")
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                print(f"   - Sınıflar: {data.get('names', {})}")
                print(f"   - Train: {data.get('train', 'Tanımsız')}")
                print(f"   - Valid: {data.get('val', 'Tanımsız')}")
            except Exception as e:
                print(f"   - YAML okuma hatası: {e}")
        else:
            print(f" data.yaml bulunamadı")
    
    def train_model(self, data_yaml_path, epochs=20, img_size=640, batch_size=4):
        """YOLOv8 modeli eğit - Düzeltilmiş"""
        
        # data.yaml yolunu ve içeriğini kontrol et
        if not os.path.exists(data_yaml_path):
            print(f" data.yaml bulunamadı: {data_yaml_path}")
            return None
            
        print(f" data.yaml kontrol ediliyor: {data_yaml_path}")
        
        # data.yaml'ı düzelt
        fixed_yaml = self.fix_data_yaml(os.path.dirname(data_yaml_path))
        if fixed_yaml:
            data_yaml_path = fixed_yaml
        
        # Veri seti yapısını kontrol et
        self.verify_dataset_structure(os.path.dirname(data_yaml_path))
        
        print("\n Model eğitimi başlatılıyor...")
        print(f"   - Epochs: {epochs}")
        print(f"   - Image Size: {img_size}")
        print(f"   - Batch Size: {batch_size}")
        print(f"   - Data YAML: {data_yaml_path}")
        
        try:
            # YOLOv8 nano model (hızlı eğitim için)
            model = YOLO('yolov8n.pt')
            
            # Eğitim parametreleri
            results = model.train(
                data=data_yaml_path,
                epochs=epochs,
                imgsz=img_size,
                batch=batch_size,
                workers=1,
                cache=False,
                name=f'{self.project_name}_training',
                patience=20,  # Erken durdurma için sabır
                save=True,
                exist_ok=True,
                pretrained=True,
                optimizer='AdamW',  # Daha kararlı optimizer
                verbose=True,
                seed=42,
                deterministic=True,
                single_cls=False,
                rect=False,
                cos_lr=True,  # Cosine learning rate
                close_mosaic=10,
                resume=False,
                amp=True,  # Mixed precision
                fraction=1.0,
                profile=False,
                # Data augmentation parametreleri
                hsv_h=0.015,
                hsv_s=0.7,
                hsv_v=0.4,
                degrees=0.0,
                translate=0.1,
                scale=0.5,
                shear=0.0,
                perspective=0.0,
                flipud=0.0,
                fliplr=0.5,
                mosaic=1.0,
                mixup=0.0,
                copy_paste=0.0
            )
            
            # En iyi modeli kaydet
            best_model_path = os.path.join(self.model_dir, "best_helmet_model.pt")
            
            # Eğitim sonucu modelini kopyala
            run_dir = f"runs/detect/{self.project_name}_training"
            if os.path.exists(f"{run_dir}/weights/best.pt"):
                shutil.copy2(f"{run_dir}/weights/best.pt", best_model_path)
                print(f" Model kaydedildi: {best_model_path}")
            else:
                print("En iyi model dosyası bulunamadı, mevcut modeli kaydediyorum...")
                model.save(best_model_path)
            
            print(f" Model eğitimi tamamlandı!")
            print(f" Model dosyası: {best_model_path}")
            
            return best_model_path
            
        except Exception as e:
            print(f" Model eğitim hatası: {e}")
            print(f"Hata detayı: {str(e)}")
            return None
    
    def evaluate_model(self, model_path, data_yaml_path):
        """Modeli değerlendir"""
        if not os.path.exists(model_path):
            print(f" Model dosyası bulunamadı: {model_path}")
            return None
            
        print(" Model değerlendiriliyor...")
        try:
            model = YOLO(model_path)
            results = model.val(data=data_yaml_path)
            
            print(f"mAP@0.5: {results.box.map50:.4f}")
            print(f"mAP@0.5:0.95: {results.box.map:.4f}")
            
            return results
        except Exception as e:
            print(f" Model değerlendirme hatası: {e}")
            return None

class HelmetDetectionSystem:
    """Gelişmiş baret tespit sistemi - Düzeltilmiş"""
    
    def __init__(self, model_path=None, database_path="safety_logs.db"):
        """
        İş güvenliği baret tespit sistemi
        """
        
        # Model yükleme
        if model_path and os.path.exists(model_path):
            try:
                self.model = YOLO(model_path)
                print(f" Özel model yüklendi: {model_path}")
            except Exception as e:
                print(f" Özel model yüklenemedi ({e}), varsayılan model kullanılıyor...")
                self.model = YOLO('yolov8n.pt')
        else:
            print("Varsayılan YOLOv8 modeli kullanılıyor...")
            self.model = YOLO('yolov8n.pt')
        
        self.database_path = database_path
        self.setup_database()
        
        # Tespit eşikleri
        self.confidence_threshold = 0.3  # Daha düşük eşik
        
        # Sınıf isimleri (modelinize göre güncelleyin)
        self.helmet_classes = ['helmet', 'hardhat', 'safety helmet', 'safety_helmet', 'hard hat', 'hat']
        self.person_classes = ['person', 'worker', 'human']
        self.no_helmet_classes = ['no-helmet', 'no_helmet', 'without_helmet', 'head']
        # YENİ: Yelek sınıfları
        self.vest_classes = ['vest', 'safety vest', 'safety_vest', 'hi-vis', 'high-vis', 'reflective vest', 'hi_vis']
        self.no_vest_classes = ['no-vest', 'no_vest', 'without_vest']
        # YENİ: Gözlük sınıfları
        self.goggles_classes = ['goggles', 'safety goggles', 'safety_goggles', 'glasses', 'eye protection', 'eye_protection']
        self.no_goggles_classes = ['no-goggles', 'no_goggles', 'without_goggles']
                
        # Performans takibi
        self.frame_count = 0
        self.detection_stats = {
            'total_persons': 0,
            'helmeted_persons': 0,
            'violations': 0
        }
    def get_test_results_report(self, days=7):
        """Test sonuçları raporu"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Test kayıtlarını al
            cursor.execute('''
                SELECT violation_type, COUNT(*) as count,
                    AVG(confidence) as avg_confidence,
                    MIN(timestamp) as first_test,
                    MAX(timestamp) as last_test
                FROM safety_violations 
                WHERE timestamp >= datetime('now', '-{} days')
                AND (violation_type LIKE 'Test%' OR worker_id = 'test_session')
                GROUP BY violation_type
                ORDER BY count DESC
            '''.format(days))
            
            results = cursor.fetchall()
            conn.close()
            
            print(f"🧪 Son {days} Gün Test Sonuçları:")
            print("=" * 60)
            
            if results:
                for row in results:
                    test_type, count, avg_conf, first, last = row
                    print(f" {test_type}")
                    print(f"   Toplam: {count} tespit")
                    print(f"   Ortalama Güven: {avg_conf:.2f}")
                    print(f"    İlk: {first}")
                    print(f"    Son: {last}")
                    print("-" * 40)
            else:
                print("Test kaydı bulunamadı!")
                
            return results
            
        except Exception as e:
            print(f" Test raporu hatası: {e}")
            return []

    def setup_database(self):
        """Veritabanı kurulumu"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS safety_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    violation_type TEXT,
                    location TEXT,
                    confidence REAL,
                    image_path TEXT,
                    worker_id TEXT,
                    status TEXT DEFAULT 'active',
                    resolved_at TEXT,
                    notes TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS detection_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    location TEXT,
                    total_persons INTEGER,
                    helmeted_persons INTEGER,
                    violations INTEGER,
                    compliance_rate REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            print(" Veritabanı hazır")
        except Exception as e:
            print(f" Veritabanı kurulum hatası: {e}")
    
    def detect_objects(self, frame):
        """Nesne tespiti yap"""
        try:
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            
            detections = {
                'helmets': [],
                'persons': [],
                'no_helmets': [],
                'vests' : [],
                'no_vests' : [],
                'goggles' : [],
                'no_goggles' : []
            }
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        class_id = int(box.cls)
                        class_name = self.model.names[class_id].lower()
                        confidence = float(box.conf)
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        
                        detection_info = {
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': confidence,
                            'center': [(x1 + x2) / 2, (y1 + y2) / 2],
                            'class_name': class_name,
                            'class_id': class_id
                        }
                        
                        # Sınıf kategorilerine ayır
                        if any(helmet_class in class_name for helmet_class in self.helmet_classes):
                            detections['helmets'].append(detection_info)
                        elif any(person_class in class_name for person_class in self.person_classes):
                            detections['persons'].append(detection_info)
                        elif any(no_helmet_class in class_name for no_helmet_class in self.no_helmet_classes):
                            detections['no_helmets'].append(detection_info)
                        elif any(vest_class in class_name for vest_class in self.vest_classes):
                            detections['vests'].append(detection_info)
                        elif any(no_vest_class in class_name for no_vest_class in self.no_vest_classes):
                            detections['no_vests'].append(detection_info)
                        elif any(goggles_class in class_name for goggles_class in self.goggles_classes):
                            detections['goggles'].append(detection_info)
                        elif any(no_goggles_class in class_name for no_goggles_class in self.no_goggles_classes):
                            detections['no_goggles'].append(detection_info)
                                                            
            return detections
            
        except Exception as e:
            print(f" Tespit hatası: {e}")
            return {'helmets': [], 'persons': [], 'no_helmets': []}
    
    def check_safety_compliance(self, detections):
        """Baret uyumunu kontrol et"""
        persons = detections['persons']
        helmets = detections['helmets']
        
        violations = []
        safe_persons = []
        
        for i, person in enumerate(persons):
            person_center = person['center']
            person_bbox = person['bbox']
            helmet_found = False
            
            # Kişinin baş bölgesi
            head_region_height = (person_bbox[3] - person_bbox[1]) * 0.4
            head_region = [
                person_bbox[0] - 20, person_bbox[1], 
                person_bbox[2] + 20, person_bbox[1] + head_region_height
            ]
            
            # En yakın bareti bul
            min_distance = float('inf')
            best_helmet = None
            
            for helmet in helmets:
                helmet_center = helmet['center']
                
                # Mesafe hesapla
                distance = np.sqrt((person_center[0] - helmet_center[0])**2 + 
                                 (person_center[1] - helmet_center[1])**2)
                
                # Baret kişinin üstünde mi?
                helmet_above_person = helmet_center[1] < person_center[1]
                
                # Baret baş bölgesinde mi?
                helmet_in_head_region = (
                    helmet_center[0] >= head_region[0] and
                    helmet_center[0] <= head_region[2] and
                    helmet_center[1] >= head_region[1] and
                    helmet_center[1] <= head_region[3]
                )
                
                if (distance < min_distance and 
                    helmet_above_person and 
                    helmet_in_head_region and
                    distance < 100):  # Maksimum mesafe
                    min_distance = distance
                    best_helmet = helmet
                    helmet_found = True
            
            if helmet_found:
                safe_persons.append({
                    'person': person,
                    'helmet': best_helmet,
                    'person_id': i
                })
            else:
                violations.append({
                    'person_id': i,
                    'person': person
                })
                
        for i, person in enumerate(persons):
            person_center = person['center']
            person_bbox = person['bbox']
            vest_found = False
            
            # Kişinin gövde bölgesi (yelek için)
            torso_region_height = (person_bbox[3] - person_bbox[1]) * 0.6
            torso_region = [
                person_bbox[0] - 10, person_bbox[1] + torso_region_height * 0.2,
                person_bbox[2] + 10, person_bbox[3] - torso_region_height * 0.2
            ]
            
            # En yakın yeleki bul
            for vest in detections['vests']:
                vest_center = vest['center']
                
                # Yelek gövde bölgesinde mi?
                vest_in_torso = (
                    vest_center[0] >= torso_region[0] and
                    vest_center[0] <= torso_region[2] and
                    vest_center[1] >= torso_region[1] and
                    vest_center[1] <= torso_region[3]
                )
                
                if vest_in_torso:
                    vest_found = True
                    break
            
            if not vest_found:
                # Mevcut violations listesindeki bu kişiyi bul ve yelek ihlali ekle
                existing_violation = next((v for v in violations if v['person_id'] == i), None)
                if existing_violation:
                    existing_violation['violations'] = existing_violation.get('violations', ['no_helmet']) + ['no_vest']
                else:
                    violations.append({
                        'person_id': i,
                        'person': person,
                        'violations': ['no_vest']
                    })
        # Gözlük kontrolü
        for i, person in enumerate(persons):
            person_center = person['center']
            person_bbox = person['bbox']
            goggles_found = False
            
            # Kişinin göz bölgesi (gözlük için)
            eye_region_height = (person_bbox[3] - person_bbox[1]) * 0.3
            eye_region = [
                person_bbox[0] - 15, person_bbox[1] + eye_region_height * 0.1,
                person_bbox[2] + 15, person_bbox[1] + eye_region_height * 0.8
            ]
            
            # En yakın gözlüğü bul
            for goggles in detections['goggles']:
                goggles_center = goggles['center']
                
                # Gözlük göz bölgesinde mi?
                goggles_in_eye_region = (
                    goggles_center[0] >= eye_region[0] and
                    goggles_center[0] <= eye_region[2] and
                    goggles_center[1] >= eye_region[1] and
                    goggles_center[1] <= eye_region[3]
                )
                
                if goggles_in_eye_region:
                    goggles_found = True
                    break
            
            if not goggles_found:
                # Mevcut violations listesindeki bu kişiyi bul ve gözlük ihlali ekle
                existing_violation = next((v for v in violations if v['person_id'] == i), None)
                if existing_violation:
                    existing_violation['violations'] = existing_violation.get('violations', []) + ['no_goggles']
                else:
                    violations.append({
                        'person_id': i,
                        'person': person,
                        'violations': ['no_goggles']
                    })
        
        return violations, safe_persons
    
    def draw_detections(self, frame, detections, violations, safe_persons):
        """Tespitleri çiz"""
        try:
            # Baretleri çiz (yeşil)
            for helmet in detections['helmets']:
                x1, y1, x2, y2 = helmet['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"Baret {helmet['confidence']:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Güvenli kişileri çiz (mavi)
            for safe in safe_persons:
                person = safe['person']
                x1, y1, x2, y2 = person['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(frame, "✓ GÜVENLİ", 
                           (x1, y1-30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(frame, f"Kişi {person['confidence']:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
            # İhlalleri çiz (kırmızı)
            for violation in violations:
                person = violation['person']
                x1, y1, x2, y2 = person['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                
                cv2.putText(frame, " BARET YOK!", 
                           (x1, y1-50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.putText(frame, "GÜVENLİK İHLALİ", 
                           (x1, y1-30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                cv2.putText(frame, f"Güven: {person['confidence']:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                
                # Kırmızı uyarı çemberi
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                cv2.circle(frame, (center_x, center_y), 50, (0, 0, 255), 3)
                
            for vest in detections['vests']:
                x1, y1, x2, y2 = vest['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                cv2.putText(frame, f"Yelek {vest['confidence']:.2f}", 
                        (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                
            # Gözlükleri çiz (turuncu)
            for goggles in detections['goggles']:
                x1, y1, x2, y2 = goggles['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
                cv2.putText(frame, f"Gozluk {goggles['confidence']:.2f}", 
                        (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)

            # İhlal çizimini güncelleyin:
            for violation in violations:
                person = violation['person']
                x1, y1, x2, y2 = person['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                
                violations_list = violation.get('violations', ['unknown'])
                violation_text = []
                if 'no_helmet' in violations_list:
                    violation_text.append("BARET")
                if 'no_vest' in violations_list:
                    violation_text.append("YELEK")
                if 'no_goggles' in violations_list:
                    violation_text.append("GOZLUK")

                if violation_text:
                    text = f" {' + '.join(violation_text)} YOK!"
                    cv2.putText(frame, text, 
                            (x1, y1-70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
            return frame
            
        except Exception as e:
            print(f" Çizim hatası: {e}")
            return frame
    
    def add_info_panel(self, frame, violations_count, safe_count, total_persons):
        """Bilgi paneli ekle"""
        try:
            overlay = frame.copy()
            cv2.rectangle(overlay, (10, 10), (400, 140), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            
            compliance_rate = (safe_count / max(total_persons, 1)) * 100
            
            info_lines = [
                f" İş Güvenliği Sistemi",
                f" Toplam Kişi: {total_persons}",
                f" Güvenli: {safe_count}",
                f" İhlal: {violations_count}",
                f" Uyum: %{compliance_rate:.1f}",
                f" {datetime.datetime.now().strftime('%H:%M:%S')}"
            ]
            
            colors = [(255, 255, 255), (255, 255, 255), (0, 255, 0), 
                     (0, 0, 255), (255, 255, 0), (200, 200, 200)]
            
            for i, (line, color) in enumerate(zip(info_lines, colors)):
                cv2.putText(frame, line, (15, 30 + i*18), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            return frame
            
        except Exception as e:
            print(f" Panel hatası: {e}")
            return frame
    
    def log_violation(self, violation_type, location, confidence, worker_id=None):
        """İhlali kaydet"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO safety_violations 
                (timestamp, violation_type, location, confidence, worker_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, violation_type, location, confidence, worker_id))
            
            conn.commit()
            conn.close()
            
            print(f" İHLAL: {timestamp} - {violation_type}")
            
        except Exception as e:
            print(f" Kayıt hatası: {e}")
    
    def process_camera_feed(self, camera_source=0, camera_name="Ana Kamera"):
        """Kamera besleme işlemi - Video için geliştirilmiş"""
        
        # İstatistik değişkenleri
        stats = {
            'total_frames': 0,
            'total_persons': 0,
            'total_helmets': 0,
            'persons_with_helmet': 0,
            'persons_without_helmet': 0,
            'total_vests': 0,
            'total_goggles' : 0
        }
        
        # Video mu kamera mı kontrol et
        is_video_file = isinstance(camera_source, str) and os.path.exists(camera_source)
        
        print(f"Kaynak: {'Video Dosyası' if is_video_file else 'Kamera'}")
        
        cap = cv2.VideoCapture(camera_source)
        
        if not cap.isOpened():
            print(f" Kaynak açılamadı: {camera_source}")
            return
        
        # Video dosyası için ek ayarlar
        if is_video_file:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_delay = int(1000 / fps) if fps > 0 else 33  # milisaniye
            print(f" Video FPS: {fps}, Frame gecikme: {frame_delay}ms")
            print(f" Toplam frame: {total_frames}")
        else:
            # Kamera ayarları
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            frame_delay = 1
            total_frames = -1
        
        print(f" {camera_name} başlatıldı...")
        print("Kontroller: 'q' = Çıkış, 's' = Ekran görüntüsü, 'p' = Duraklat")
        
        frame_count = 0
        paused = False
        
        while True:
            if not paused:
                ret, frame = cap.read()
                
                if not ret:
                    if is_video_file:
                        print(" Video sonu - Çıkılıyor...")
                        break
                    else:
                        print(" Kameradan görüntü alınamıyor!")
                        break
                
                frame_count += 1
                stats['total_frames'] += 1
                
                # Her frame'i işle (performans için azaltılabilir)
                if frame_count % 2 == 0:  # Her 2 frame'de bir işle
                    try:
                        # Nesne tespiti
                        detections = self.detect_objects(frame)
                        
                        # İstatistikleri güncelle
                        current_persons = len(detections['persons'])
                        current_helmets = len(detections['helmets'])
                        current_vests = len(detections['vests'])
                        current_goggles = len(detections.get('goggles', []))

                        
                        stats['total_persons'] += current_persons
                        stats['total_helmets'] += current_helmets
                        stats['total_vests'] += current_vests
                        stats['total_goggles'] += current_goggles
 
                        
                        # Baret uyumu kontrolü
                        violations, safe_persons = self.check_safety_compliance(detections)
                        
                        # Güvenli ve ihlal sayılarını güncelle
                        stats['persons_with_helmet'] += len(safe_persons)
                        stats['persons_without_helmet'] += len(violations)
                        
                        # İstatistikler
                        total_persons = len(detections['persons'])
                        safe_count = len(safe_persons)
                        violations_count = len(violations)
                        
                        # Anlık durumu yazdır
                        if frame_count % 30 == 0:  # Her 30 frame'de bir güncelle
                            print(f"\n Anlık Durum (Frame {frame_count}):")
                            print(f" Tespit Edilen Kişi: {current_persons}")
                            print(f" Tespit Edilen Baret: {current_helmets}")
                            print(f" Tespit Edilen Yelek: {current_vests}")
                            print(f" Baretli Kişi: {len(safe_persons)}")
                            print(f" Baretsiz Kişi: {len(violations)}")
                            print(f" Tespit Edilen Gözlük: {current_goggles}")

                        
                        # Çizimleri yap
                        frame = self.draw_detections(frame, detections, violations, safe_persons)
                        frame = self.add_info_panel(frame, violations_count, safe_count, total_persons)
                        
                        # Video için ilerleme bilgisi
                        if is_video_file and total_frames > 0:
                            progress = (frame_count / total_frames) * 100
                            cv2.putText(frame, f"İlerleme: %{progress:.1f}", 
                                      (10, frame.shape[0] - 10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        
                    except Exception as e:
                        print(f" İşlem hatası: {e}")
            
            # Görüntüyü göster
            cv2.imshow(f" İş Güvenliği - {camera_name}", frame)
            
            # Klavye kontrolü
            key = cv2.waitKey(frame_delay) & 0xFF
            if key == ord('q'):
                print(" Çıkılıyor...")
                break
            elif key == ord('s'):
                # Ekran görüntüsü kaydet
                os.makedirs("screenshots", exist_ok=True)
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                screenshot_path = f"screenshots/{camera_name}_{timestamp}.jpg"
                cv2.imwrite(screenshot_path, frame)
                print(f" Kaydedildi: {screenshot_path}")
            elif key == ord('p'):
                # Duraklat/Devam et (sadece video için)
                if is_video_file:
                    paused = not paused
                    print("Duraklatıldı" if paused else " Devam")
        
        # İşlem sonunda istatistikleri göster
        print("\n TOPLAM İSTATİSTİKLER:")
        print("=" * 40)
        print(f"Toplam Frame: {stats['total_frames']}")
        print(f" Toplam Tespit Edilen Kişi: {stats['total_persons']}")
        print(f" Toplam Tespit Edilen Baret: {stats['total_helmets']}")
        print(f" Toplam Tespit Edilen Yelek: {stats['total_vests']}")
        print(f" Toplam Baretli Kişi Tespiti: {stats['persons_with_helmet']}")
        print(f" Toplam Baretsiz Kişi Tespiti: {stats['persons_without_helmet']}")
        print(f" Toplam Tespit Edilen Gözlük: {stats['total_goggles']}")

        
        if stats['total_persons'] > 0:
            helmet_rate = (stats['persons_with_helmet'] / stats['total_persons']) * 100
            print(f" Baret Kullanım Oranı: %{helmet_rate:.2f}")
        
        cap.release()
        cv2.destroyAllWindows()
        print(" İşlem tamamlandı!")

    def get_violation_report(self, days=7):
        """İhlal raporu al"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Son N gün içindeki ihlalleri al
            cursor.execute('''
                SELECT violation_type, location, COUNT(*) as count,
                       AVG(confidence) as avg_confidence,
                       MIN(timestamp) as first_violation,
                       MAX(timestamp) as last_violation
                FROM safety_violations 
                WHERE timestamp >= datetime('now', '-{} days')
                GROUP BY violation_type, location
                ORDER BY count DESC
            '''.format(days))
            
            results = cursor.fetchall()
            conn.close()
            
            print(f"\ Son {days} Gün İhlal Raporu:")
            print("=" * 60)
            
            if results:
                for row in results:
                    violation_type, location, count, avg_conf, first, last = row
                    print(f" {location}")
                    print(f"    İhlal Türü: {violation_type}")
                    print(f"   Toplam: {count} kez")
                    print(f"    Ortalama Güven: {avg_conf:.2f}")
                    print(f"    İlk: {first}")
                    print(f"    Son: {last}")
                    print("-" * 40)
            else:
                print(" İhlal bulunamadı!")
                
            return results
            
        except Exception as e:
            print(f" Rapor hatası: {e}")
            return []

# Hızlı başlatma fonksiyonları
def quick_start_with_roboflow_dataset():
    """Roboflow veri seti ile hızlı başlatma"""
    
    # Sizin Roboflow bilgileriniz
    ROBOFLOW_API_KEY = None  # Buraya API key'inizi yazın
    WORKSPACE = "yazlmmuhdemo"
    PROJECT = "hard-hat-detector-znysj-wwk5m"
    VERSION = 1
    
    print(" Roboflow veri seti ile eğitim başlatılıyor...")
    
    trainer = HelmetDetectionTrainer()
    
    # Veri setini indir
    dataset_path = trainer.download_roboflow_dataset(
        api_key=ROBOFLOW_API_KEY,
        workspace=WORKSPACE,
        project=PROJECT,
        version=VERSION
    )
    
    if dataset_path:
        # data.yaml yolunu bul
        data_yaml_path = os.path.join(dataset_path, "data.yaml")
        
        # Modeli eğit
        model_path = trainer.train_model(
            data_yaml_path=data_yaml_path,
            epochs=20,  # Hızlı test için azaltıldı
            batch_size=4
        )
        
        if model_path:
            # Tespit sistemini başlat
            detector = HelmetDetectionSystem(model_path=model_path)
            detector.process_camera_feed(camera_source=0)
        else:
            print("Model eğitimi başarısız, varsayılan model ile devam ediliyor...")
            detector = HelmetDetectionSystem()
            detector.process_camera_feed(camera_source=0)
    else:
        print("Veri seti indirilemedi!")

def quick_start_detection_only():
    """Sadece tespit sistemi (eğitim olmadan)"""
    print(" Hızlı tespit sistemi başlatılıyor...")
    
    detector = HelmetDetectionSystem()
    detector.process_camera_feed(camera_source=0)

def train_with_custom_dataset(dataset_path):
    """Özel veri seti ile eğitim"""
    print(f" Özel veri seti ile eğitim: {dataset_path}")
    
    trainer = HelmetDetectionTrainer()
    
    # data.yaml yolunu bul
    data_yaml_path = os.path.join(dataset_path, "data.yaml")
    
    if not os.path.exists(data_yaml_path):
        print(f" data.yaml bulunamadı: {data_yaml_path}")
        return
    
    # Modeli eğit
    model_path = trainer.train_model(
        data_yaml_path=data_yaml_path,
        epochs=20,
        batch_size=8
    )
    
    if model_path:
        # Modeli değerlendir
        trainer.evaluate_model(model_path, data_yaml_path)
        
        # Tespit sistemini başlat
        detector = HelmetDetectionSystem(model_path=model_path)
        detector.process_camera_feed(camera_source=0)
    else:
        print(" Model eğitimi başarısız!")

def generate_safety_report():
    """Güvenlik raporu oluştur - Test kayıtları dahil"""
    print(" Güvenlik raporu oluşturuluyor...")
    
    detector = HelmetDetectionSystem()
    
    # Haftalık rapor (Test dahil)
    print("\n=== HAFTALİK RAPOR ===")
    detector.get_violation_report(days=7)
    
    # Test sonuçları raporu
    print("\n=== TEST SONUÇLARI ===")
    detector.get_test_results_report(days=7)
    
    # Aylık rapor
    print("\n=== AYLIK RAPOR ===")
    detector.get_violation_report(days=30)

def demo_with_video_file(video_path):
    """Video dosyası ile özel modelle demo - Geliştirilmiş hata kontrolü"""
    print(f" Video ile demo: {video_path}")
    
    # Model yolu kontrolü
    model_path = "models/helmet_detection/best_helmet_model.pt"
    if not os.path.exists(model_path):
        print(f" Model dosyası bulunamadı: {model_path}")
        print("Önce modeli eğitmeniz gerekiyor.")
        return
    
    print(f" Özel model yüklendi: {model_path}")
    
    # Dosya yolu kontrolü
    video_path = os.path.abspath(video_path)  # Mutlak yolu al
    if not os.path.exists(video_path):
        print(f" Video dosyası bulunamadı: {video_path}")
        print("Lütfen dosya yolunu kontrol edin.")
        return
    
    # Video formatı kontrolü
    video_ext = os.path.splitext(video_path)[1].lower()
    supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    
    if video_ext not in supported_formats:
        print(f" Desteklenmeyen video formatı: {video_ext}")
        print(f"Desteklenen formatlar: {', '.join(supported_formats)}")
        return
    
    # Video açma denemesi
    print(" Video dosyası test ediliyor...")
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f" Video açılamadı: {video_path}")
        print("\nOlası sebepler:")
        print("1. Video dosyası bozuk olabilir")
        print("2. Codec desteklenmiyor olabilir")
        print("3. Dosya yolunda Türkçe karakter var")
        print("4. Dosya başka bir program tarafından kullanılıyor")
        print("\nÖneriler:")
        print("1. Video dosyasını MP4 formatına dönüştürün")
        print("2. Dosya adında Türkçe karakter ve boşluk kullanmayın")
        print("3. Dosyayı C:\\ gibi kısa bir yola taşıyın")
        cap.release()
        return
    
    # Video bilgilerini al
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"\n Video başarıyla açıldı!")
    print(f"Video bilgileri:")
    print(f"- Boyut: {width}x{height}")
    print(f"- FPS: {fps}")
    print(f"- Toplam frame: {frame_count}")
    
    cap.release()
    
    # Tespit sistemini başlat - Özel model ile
    detector = HelmetDetectionSystem(model_path=model_path)
    detector.process_camera_feed(camera_source=video_path, camera_name="Video Demo")

def run_test_model(model_path):
   
    # Model yükle
    model = YOLO(model_path)
    
    # Video kayıt ayarları
    os.makedirs("test_videos", exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_video_path = f"test_videos/test_session_{timestamp}.mp4"

    # Video kaydedici kurulumu
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = None
    frame_width, frame_height = 1280, 720

    def log_test_detection(detection_type, confidence, location="Test"):
        try:
            conn = sqlite3.connect("safety_logs.db")
            cursor = conn.cursor()
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO safety_violations 
                (timestamp, violation_type, location, confidence, worker_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, detection_type, location, confidence, "test_session"))
            
            conn.commit()
            conn.close()
            print(f" Test kaydı: {detection_type} - Güven: {confidence:.2f}")
            
        except Exception as e:
            print(f"Test kayıt hatası: {e}")

    # Tahmin yap
    results = model.predict(
        source=0,
        show=True,
        conf=0.5,
        imgsz=640,
        stream=True,
        save=False
    )

    print(" Test modunda çalışıyor - Tespitler ve video kaydediliyor...")
    print(f"Video kaydediliyor: {output_video_path}")
    print("'q' tuşuna basarak çıkabilirsiniz...")

    for result in results:
        if video_writer is None and result.orig_img is not None:
            frame_height, frame_width = result.orig_img.shape[:2]
            video_writer = cv2.VideoWriter(output_video_path, fourcc, 20.0, (frame_width, frame_height))
            print(f" Video kaydedici başlatıldı: {frame_width}x{frame_height}")

        if video_writer is not None and result.orig_img is not None:
            annotated_frame = result.plot()
            video_writer.write(annotated_frame)

        if result.boxes is not None:
            for box in result.boxes:
                class_id = int(box.cls)
                class_name = model.names[class_id].lower()
                confidence = float(box.conf)

                if 'helmet' in class_name or 'hardhat' in class_name:
                    log_test_detection("Test - Baret Tespit", confidence)
                elif 'vest' in class_name or 'safety' in class_name:
                    log_test_detection("Test - Yelek Tespit", confidence)
                elif 'person' in class_name:
                    log_test_detection("Test - Kişi Tespit", confidence)
                elif 'no-helmet' in class_name:
                    log_test_detection("Test - Baret Kullanmama", confidence)
                elif 'no-vest' in class_name:
                    log_test_detection("Test - Yelek Kullanmama", confidence)

                print(f" Tespit: {class_name} - Güven: {confidence:.2f}")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if video_writer is not None:
        video_writer.release()
        print(f" Video kaydedildi: {output_video_path}")
    else:
        print(" Video kaydedilemedi!")

    cv2.destroyAllWindows()

def troubleshoot_video_issues():
    """Video sorunları için detaylı kontrol"""
    print(" Video Sorun Giderme Aracı")
    print("=" * 40)
    
    video_path = input("Problem olan video dosyasının yolunu girin: ").strip()
    
    if not os.path.exists(video_path):
        print(f" Dosya bulunamadı: {video_path}")
        return
    
    print(f" Dosya bulundu: {video_path}")
    
    # Dosya bilgileri
    file_size = os.path.getsize(video_path) / (1024 * 1024)
    file_ext = os.path.splitext(video_path)[1].lower()
    
    print(f" Dosya boyutu: {file_size:.2f} MB")
    print(f" Dosya formatı: {file_ext}")
    
    # Desteklenen formatları kontrol et
    supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    if file_ext not in supported_formats:
        print(f" Desteklenmeyen video formatı!")
        print(f"Desteklenen formatlar: {', '.join(supported_formats)}")
    
    # Dosya yolu kontrolü
    if any(c in video_path for c in 'çğıöşüÇĞİÖŞÜ '):
        print(" Dosya yolunda Türkçe karakter veya boşluk var!")
        print("Önerilen: Dosyayı Türkçe karakter ve boşluk içermeyen bir yola taşıyın")
        print("Örnek: C:\\Videos\\test.mp4")
    
    # OpenCV testi
    print("\n OpenCV ile test ediliyor...")
    cap = cv2.VideoCapture(video_path)
    
    if cap.isOpened():
        print(" OpenCV dosyayı açabildi")
        
        # Video özelliklerini al
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"   Boyut: {width}x{height}")
        print(f"    FPS: {fps}")
        print(f"   Frame sayısı: {frame_count}")
        
        # İlk frame'i oku
        ret, frame = cap.read()
        if ret:
            print(" Frame okuma başarılı")
            
            # Birkaç frame daha test et
            success_count = 0
            for i in range(10):
                ret, _ = cap.read()
                if ret:
                    success_count += 1
            
            print(f"10 frame testinden {success_count} tanesi başarılı")
            
            if success_count < 10:
                print(" Bazı frame'ler okunamadı - video bozuk olabilir")
        else:
            print("Frame okunamadı - video bozuk olabilir")
        
        cap.release()
        
        # Öneriler
        print("\n Öneriler:")
        if success_count < 10:
            print("1. Videoyu başka bir program ile açıp kontrol edin")
            print("2. Videoyu yeniden kodlayın (re-encode)")
            print("3. Videoyu MP4 formatına dönüştürün")
            print("4. Daha küçük bir video ile test edin")
    else:
        print(" OpenCV dosyayı açamadı")
        print("\nÇözüm önerileri:")
        print("1. Video formatını kontrol edin")
        print("2. Videoyu MP4 formatına dönüştürün")
        print("3. Dosyayı kısa bir yola taşıyın (örn: C:\\Videos\\)")
        print("4. Dosya adından Türkçe karakterleri kaldırın")
        print("5. Başka bir video oynatıcı ile test edin")

def main():
    """Ana menü"""
    print(" İş Güvenliği Baret Tespit Sistemi")
    print("=" * 50)
    print("1. Roboflow veri seti ile eğitim + tespit")
    print("2. Sadece canlı tespit (eğitim yok)")
    print("3. Özel veri seti ile eğitim")
    print("4. Güvenlik raporu görüntüle")
    print("5. Video dosyası ile demo")
    print("6. Test modu (kayıtlı model ile)")
    print("7. Video sorun giderme aracı")  # YENİ
    print("8. Çıkış")
    
    while True:
        try:
            choice = input("\nSeçiminizi yapın (1-8): ").strip()
            
            if choice == "1":
                print("\n Roboflow API key'ini koda girmeyi unutmayın!")
                quick_start_with_roboflow_dataset()
                break
                
            elif choice == "2":
                quick_start_detection_only()
                break
                
            elif choice == "3":
                dataset_path = input("Veri seti yolunu girin: ").strip()
                train_with_custom_dataset(dataset_path)
                break
                
            elif choice == "4":
                generate_safety_report()
                
            elif choice == "5":
                video_path = input("Video dosya yolunu girin: ").strip()
                demo_with_video_file(video_path)
                break
                
            elif choice == "6":
                model_path = "models/helmet_detection/best_helmet_model.pt"
                if os.path.exists(model_path):
                    print(" Test modu başlatılıyor...")
                    run_test_model(model_path)
                else:
                    print(" Model dosyası bulunamadı!")
                    
            elif choice == "7":  # YENİ
                troubleshoot_video_issues()
                    
            elif choice == "8":
                print(" Güle güle!")
                break
                
            else:
                print(" Geçersiz seçim! 1-8 arası bir sayı girin.")
                
        except KeyboardInterrupt:
            print("\n\n Program sonlandırıldı!")
            break
        except Exception as e:
            print(f" Hata: {e}")

if __name__ == "__main__":
    # Sistem kontrolleri
    print(" Sistem kontrolleri yapılıyor...")
    
    # Gerekli dizinleri oluştur
    os.makedirs("datasets", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    print(" Sistem hazır!")
    
    # Ana programı başlat
    main()

"""
KULLANIM KILAVUZU:
================

1. GEREKLİ PAKETLER:
   pip install ultralytics roboflow opencv-python pillow numpy requests pyyaml

2. ROBOFLOW İLE KULLANIM:
   - Roboflow hesabınızdan API key alın
   - quick_start_with_roboflow_dataset() fonksiyonundaki ROBOFLOW_API_KEY değişkenine yazın
   - Workspace ve project bilgilerini güncelleyin

3. ÖZEL VERİ SETİ İLE KULLANIM:
   - Veri setinizi YOLOv8 formatında hazırlayın
   - data.yaml dosyasını doğru şekilde yapılandırın
   - train_with_custom_dataset() fonksiyonunu kullanın

4. SADECE TESPİT:
   - Eğitim yapmadan doğrudan tespit yapmak için
   - quick_start_detection_only() fonksiyonunu kullanın

5. KAMERA KAYNAKLARI:
   - 0: Varsayılan web kamerası
   - 1, 2, 3...: Diğer USB kameralar
   - "video.mp4": Video dosyası
   - "rtsp://ip:port/stream": IP kamera

6. KLAVYE KONTROLLERI:
   - 'q': Çıkış
   - 's': Ekran görüntüsü kaydet

7. VERİTABANI:
   - SQLite veritabanında ihlaller otomatik kaydedilir
   - safety_logs.db dosyasında saklanır
   - Rapor fonksiyonları ile görüntülenebilir

8. PERFORMANS İPUÇLARI:
   - GPU varsa CUDA kullanılır (otomatik)
   - Batch size'ı RAM'inize göre ayarlayın
   - confidence_threshold değerini optimize edin
   - Frame işleme oranını azaltarak performans artırın

9. GÜVENLİK ÖZELLİKLERİ:
   - Gerçek zamanlı ihlal tespiti
   - Otomatik kayıt sistemi
   - Görsel uyarılar
   - İstatistik takibi
   - Raporlama sistemi

10. SORUN GİDERME:
    - OpenCV kamera açmıyorsa: Kamera izinlerini kontrol edin
    - Model yüklenemiyorsa: YOLO paketini güncelleyin
    - Düşük FPS: Görüntü boyutunu küçültün
    - Yanlış tespit: Confidence threshold'u ayarlayın
"""