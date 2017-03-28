# -*- coding: utf-8 -*-
"""
Created on Thu Mar 02 14:16:50 2017

@author: hus20664877
"""


import ViconNexus
import numpy as np


vicon = ViconNexus.ViconNexus()

dname, dtype, drate, outputids, nfp, _ = vicon.GetDeviceDetails(1)

R = np.array(nfp.WorldR).reshape(3,3)
T = np.array(nfp.WorldT)

c1 = nfp.LowerBounds
c2 = nfp.UpperBounds

c = np.stack([c1, c2])

cw = np.dot(R, c.T).T + T

           
          
             
             
             
             
      









