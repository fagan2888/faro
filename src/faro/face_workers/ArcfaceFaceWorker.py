'''
MIT License

Copyright 2019 Oak Ridge National Laboratory

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Created on October 3, 2019

@author: srinivasn1
@ORNL
'''

import faro
import os
import faro.proto.proto_types as pt 
import faro.proto.face_service_pb2 as fsd
import numpy as np
import pyvision as pv
 

class ArcfaceFaceWorker(faro.FaceWorker):
    '''
    classdocs
    '''

    def __init__(self, options):
        '''
        Constructor
        '''
        import insightface
        kwargs = {'root':os.path.join(options.storage_dir,'models')}
        
        #load Retina face model
        self.detector = insightface.model_zoo.get_model('retinaface_r50_v1',**kwargs)
        #set ctx_id to a gpu a predefined gpu value
        self.detector.prepare(ctx_id = -1, nms=0.4)
        # load arcface FR model
        self.fr_model = insightface.model_zoo.get_model('arcface_r100_v1',**kwargs)
        
        self.fr_model.prepare(ctx_id = -1) 
                
        print("ArcFace Models Loaded.")

        
    def detect(self,img,face_records,options):
        '''Run a face detector and return rectangles.'''
        print('Running Face Detector For ArchFace')

        #print(options.threshold)
        # Run the detector on the image
        dets, lpts = self.detector.detect(img, threshold=options.threshold, scale=1)
        # Now process each face we found and add a face to the records list.
        for idx in range(0,dets.shape[0]):
            face_record = face_records.face_records.add()
            face_record.detection.score = dets[idx,-1:]
            ulx, uly, lrx, lry = dets[idx,:-1]        
            #create_square_bbox = np.amax(abs(lrx-ulx) , abs(lry-uly))
            face_record.detection.location.CopyFrom(pt.rect_val2proto(ulx, uly, abs(lrx-ulx) , abs(lry-uly)))
            face_record.detection.detection_id = idx
            face_record.detection.detection_class = "FACE_%d"%idx
            lmark = face_record.landmarks.add()
            lmarkloc = lpts[idx]
            for ldx in range(0,lmarkloc.shape[0]):
                lmark.landmark_id = "point_%02d"%ldx
                lmark.location.x = lmarkloc[ldx][0]
                lmark.location.y = lmarkloc[ldx][1]

        if options.best:
            face_records.face_records.sort(key = lambda x: -x.detection.score)
            
            while len(face_records.face_records) > 1:
                del face_records.face_records[-1]
            
        print('Done Running Face Detector For ArchFace')
    
    def locate(self,img,face_records,options):
        '''Locate facial features.'''
        pass #the 5 landmarks points that retina face detects are stored during detection
        
        
    def align(self,image,face_records):
        '''Align the images to a standard size and orientation to allow 
        recognition.'''
        pass # Not needed for this algorithm.
            
    def extract(self,img,face_records):
        '''Extract a template that allows the face to be matched.'''
        # Compute the 512D vector that describes the face in img identified by
        #shape.

        im = pv.Image(img[:,:,::-1])

        for face_record in face_records.face_records:
            rect = pt.rect_proto2pv(face_record.detection.location)
            x,y,w,h = rect.asTuple()

            # Extract view
            rect = pv.Rect()
            cx,cy = x+0.5*w,y+0.5*h
            tmp = 1.5*max(w,h)
            cw,ch = tmp,tmp
            crop = pv.AffineFromRect(pv.CenteredRect(cx,cy,cw,ch),(256,256))

            pvim = pv.Image(img[:,:,::-1]) # convert rgb to bgr
            pvim = crop(pvim)
            view = pt.image_pv2proto(pvim)
            face_record.view.CopyFrom(view)
            
            tile = pvim.resize((224,224))
            tile = tile.resize((112,112)) 
        
            face_im = tile.asOpenCV2()
            face_im = face_im[:,:,::-1] # Convert BGR to RGB
        
            features = self.fr_model.get_embedding(face_im) 
            face_descriptor = pv.meanUnit(features.flatten())
            
            face_record.template.data.CopyFrom(pt.vector_np2proto(face_descriptor))

                
    def scoreType(self):
        '''Return the method used to create a score from the template.
        
        By default server computation is required.
        
        SCORE_L1, SCORE_L2, SCORE_DOT, SCORE_SERVER
        '''
        return fsd.NEG_DOT
    
    def status(self):
        '''Return a simple status message.'''
        print("Handeling status request.")
        status_message = fsd.FaceServiceInfo()
        status_message.status = fsd.READY
        status_message.detection_support = True
        status_message.extract_support = True
        status_message.score_support = True
        status_message.score_type = self.scoreType()
        status_message.detection_threshold = self.recommendedDetectionThreshold()
        status_message.match_threshold = self.recommendedScoreThreshold()
        status_message.algorithm = "ArcFace-model arcface_r100_v1"

        
        return status_message
        

    def recommendedDetectionThreshold(self):
        
        return 0.5

    def recommendedScoreThreshold(self,far=-1):
       
        '''
        Arcface does not provide a match threshold
        '''
         
        return -0.42838144


