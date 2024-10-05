import json
from backend.emotion_detect.emotion_detector import EmotionDetector
from backend.image_object import ImageObject
from backend.landmark_detection import LandmarkDetector
from backend.overlay_accessory import overlay_accessory
import cv2
from datetime import datetime
import dlib
from imutils import face_utils
import numpy as np
import os
import datetime

camera=cv2.VideoCapture(0)
emotion_detector = EmotionDetector()

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
OBJECT_PATH_LOCAL = os.path.join('objects/objects.json')
PREDICTOR_PATH_LOCAL = os.path.join(ROOT_PATH, 'model/shape_predictor_68_face_landmarks.dat')
landmark_detector = LandmarkDetector(predictor_path=PREDICTOR_PATH_LOCAL)

with open(OBJECT_PATH_LOCAL) as json_file:
    data = json.load(json_file)
    obj_keys = data.keys()




cache = {
    'overlay_obj_index': 0,
    'emotion': []
}

class Capture():
    RESIZE_RATIO = 1.0
    def __init__(self):
        self.video=cv2.VideoCapture(0)
        self.path=os.path.dirname(os.path.realpath(__file__))
        self.path=self.path.replace('\\','/')
        
        
        #face detector and landmarks
        self.face_detecter=dlib.get_frontal_face_detector()
        self.face_landmark=dlib.shape_predictor(f'{self.path}/model/shape_predictor_68_face_landmarks.dat')
        self.mouth_start,self.mouth_end=face_utils.FACIAL_LANDMARKS_IDXS['mouth']
        self.nose_start,self.nose_end=face_utils.FACIAL_LANDMARKS_IDXS['nose']
        self.jaw_start,self.jaw_end=face_utils.FACIAL_LANDMARKS_IDXS['jaw']
        self.righteyebrow_start,self.righteyebrow_end = face_utils.FACIAL_LANDMARKS_IDXS['right_eyebrow']
        
    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, frame = self.video.read()
        if not success:
            return None

        if (Capture.RESIZE_RATIO != 1):
            frame = cv2.resize(frame, None, fx=Capture.RESIZE_RATIO, fy=Capture.RESIZE_RATIO)

        return frame
    
    def get_feed(self):
        frame = self.get_frame()
        return frame
    
    def filter(self,glass=None,save=None):
        #for computation handling
        ret,frame= self.video.read()
        frame=cv2.resize(frame,(640,480))
        frame=cv2.flip(frame,180)
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        faces=self.face_detecter(gray,0)
        
        for face in faces:
            #shape
            shape=self.face_landmark(gray,face)
            shape=face_utils.shape_to_np(shape)
            
            #geting cordinates
            nose = shape[self.nose_start:self.nose_end]
            righteyebrow = shape[self.righteyebrow_start:self.righteyebrow_end]
            jaw=shape[self.jaw_start:self.jaw_end]
            
            #for glasses
            glass_left=jaw[16][0]+35
            glass_right=jaw[2][0]-35
            glass_up = righteyebrow[2][1]-25
            glass_down = nose[4][1]+25

            glass_dist_x = glass_left-glass_right
            glass_dist_y = glass_down-glass_up
            
            #glass filter
            if not glass is None:
                if glass_left<=640 and glass_left>=0 and glass_right>=0 and glass_right<640 and glass_up<=480 and glass_down<=480 and glass_up>=0 and glass_down>=0:
                    glass=cv2.resize(glass,(glass_dist_x,glass_dist_y))
                    roi=frame[glass_up:glass_down,glass_right:glass_left]
                    img2gray=cv2.cvtColor(glass,cv2.COLOR_BGR2GRAY)
                    if glass[0][0][0] > 200:
                        _,mask=cv2.threshold(img2gray,0,255,cv2.THRESH_BINARY_INV)
                    else:
                        _,mask=cv2.threshold(img2gray,0,255,cv2.THRESH_BINARY)
                    mask_inv=cv2.bitwise_not(mask)
                    frame_bg=cv2.bitwise_and(roi,roi,mask=mask_inv)
                    glass_fg=cv2.bitwise_and(glass,glass,mask=mask)
                    roi=cv2.add(frame_bg,glass_fg)
                    frame[glass_up:glass_down,glass_right:glass_left]=roi
            nose=shape[self.nose_start:self.nose_end]
            
        if save is not None:
            now_time=datetime.now()
            current_time = now_time.strftime("%d_%m_%Y_%H_%M_%S")
            cv2.imwrite(f'static/images/userimages/{current_time}.jpg',frame)
            save=None
            
        ret,jpg=cv2.imencode('.jpg',frame)
        return jpg.tobytes()
    
        

def generate_video(camera,glass=None,save=None):
    prev_time = datetime.datetime.now()
  
    while True:
  
        frame = camera.get_feed()

        if len(list(obj_keys)) > 0:
                obj_id = list(obj_keys)[cache['overlay_obj_index']]
                # frame = face_overlay_accessory(src_img=frame, accessory_obj_id=obj_id)

                current_time = datetime.datetime.now()
                if (current_time - prev_time).total_seconds() > 0.5:
                    prev_time = current_time
                    emotion_frame = frame
                    detect_result = emotion_detector.detect(emotion_frame)
                    if detect_result:
                        [x, y, emotion_result] = detect_result
                        cache['emotion'].append(1 if emotion_result == "Happy" else 0)
                    print("from emotion")
                    print(cache)

        frame=camera.filter(glass=glass,save=save)
        
        yield(b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'+frame+b'\r\n')

def save_image():
    pass


def load_accessory_obj(obj_id):
    with open(OBJECT_PATH_LOCAL) as json_file:
        data = json.load(json_file)
        obj_json = data[obj_id]
        acc_img = cv2.imread(os.path.join(ROOT_PATH, obj_json['path']), cv2.IMREAD_UNCHANGED)
        # acc_img = cv2.imread('glasses2.png')
        acc_info = obj_json['info']
        return acc_img, acc_info

# def face_overlay_accessory(src_img, accessory_obj_id=None):
#     """ FACE OVERLAY WITH ACCESSORY """
#     margin = 1.5
#     width = 500
#     ratio = 1

#     # Load the image
#     face_landmarks = landmark_detector.detect(img=src_img)
#     face_obj = ImageObject(img=src_img, landmarks=face_landmarks, type='face')
#     # Crop the image
#     face_obj.crop(margin, ratio, width)

#     glass_img, info = load_accessory_obj(obj_id=accessory_obj_id)

#     accessory_obj = ImageObject(img=glass_img, landmarks=info, type='accessory', sub_type='glasses')

#     if not face_obj.has_face():
#         object_overlay_img = face_obj.data
#     else:
#         # Face overlay with object
#         object_overlay_img = overlay_accessory(face_obj, accessory_obj)

#     return object_overlay_img
