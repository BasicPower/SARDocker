#!/usr/bin/env python
#******************************************************************************
#  Name:     dispms.py
#  Purpose:  Display a multispectral image
#             allowed formats: uint8, uint16,float32,float64 
#  Usage (from command line):             
#    python dispms.py  
#
# MIT License
# 
# Copyright (c) 2016 Mort Canty
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys, getopt, os
from osgeo import gdal, osr
from osgeo.gdalconst import GDT_Byte
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import  auxil.auxil as auxil 
import numpy as np
from osgeo.gdalconst import GA_ReadOnly


def klm(fn,dims):
    KLM = '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Folder>
        <name>Ground Overlay</name>
        <description>Change map overlay</description>
        <GroundOverlay>
          <name>Change map overlay</name>
          <description>SAR change detection.</description>
          <Icon>
            _image_
          </Icon>
          <LatLonBox>
            <north>_north_</north>
            <south>_south_</south>
            <east>_east_</east>
            <west>_west_</west>
            <rotation>-0.0</rotation>
          </LatLonBox>
        </GroundOverlay>
      </Folder>
    </kml> '''
    try:
        imageDataset = gdal.Open(fn,GA_ReadOnly)
        cols = imageDataset.RasterXSize
        rows = imageDataset.RasterYSize           
        gt =   imageDataset.GetGeoTransform()
#      correct for subsetting
        x0,y0,cols,rows = dims
        gt = list(gt)
        gt[0] = gt[0] + x0*gt[1] + y0*gt[2]
        gt[3] = gt[3] + x0*gt[4] + y0*gt[5]
#      get footprint
        ulx = gt[0]  
        uly = gt[3]
        urx = gt[0] + cols*gt[1]
        ury = gt[3] + cols*gt[4]
        llx = gt[0]              + rows*gt[2]
        lly = gt[3]              + rows*gt[5]
        lrx = gt[0] + cols*gt[1] + rows*gt[2]
        lry = gt[3] + cols*gt[4] + rows*gt[5]
#      get image coordinate system       
        old_cs = osr.SpatialReference()
        old_cs.ImportFromWkt(imageDataset.GetProjection())
#      create the lonlat coordinate system
        new_cs = osr.SpatialReference()  
        new_cs.SetWellKnownGeogCS('WGS84')              
#      create a transform object to convert between coordinate systems
        transform = osr.CoordinateTransformation(old_cs,new_cs)                                          
#      get the bounding coordinates in lonlat (no elevation)
        coords = []
        coords.append(list(transform.TransformPoint(ulx,uly)[0:2]))      
        coords.append(list(transform.TransformPoint(urx,ury)[0:2])) 
        coords.append(list(transform.TransformPoint(llx,lly)[0:2]))
        coords.append(list(transform.TransformPoint(lrx,lry)[0:2])) 
#      get the klm LatLonBox dimensions
        north = coords[0][1]; south = coords[2][1]; east = coords[1][0] ; west = coords[0][0] 
#      edit the KLM string
        KLM = KLM.replace('_north_',str(north))   
        KLM = KLM.replace('_south_',str(south))
        KLM = KLM.replace('_east_',str(east))   
        KLM = KLM.replace('_west_',str(west))
        return KLM
    except Exception as e:
        print 'Error: %s  Could not get image footprint'%e
        return None   

def make_image(redband,greenband,blueband,rows,cols,enhance):
    X = np.ones((rows*cols,3),dtype=np.uint8) 
    if enhance == 'linear255':
        i = 0
        for tmp in [redband,greenband,blueband]:
            tmp = tmp.ravel()
            tmp = np.where(tmp<0,0,tmp)  
            tmp = np.where(tmp>255,255,tmp)
            X[:,i] = np.byte(tmp)
            i += 1
    elif enhance == 'linear':
        i = 0
        for tmp in [redband,greenband,blueband]:             
            tmp = tmp.ravel()  
            mx = np.max(tmp)
            mn = np.min(tmp)  
            if mx-mn > 0:
                tmp = (tmp-mn)*255.0/(mx-mn)    
            tmp = np.where(tmp<0,0,tmp)  
            tmp = np.where(tmp>255,255,tmp)
            X[:,i] = np.byte(tmp)
            i += 1
    elif enhance == 'linear2pc':
        i = 0
        for tmp in [redband,greenband,blueband]:     
            tmp = tmp.ravel()        
            mx = np.max(tmp)
            mn = np.min(tmp)  
            if mx-mn > 0:
                tmp = (tmp-mn)*255.0/(mx-mn)  
            tmp = np.where(tmp<0,0,tmp)  
            tmp = np.where(tmp>255,255,tmp)
            hist,bin_edges = np.histogram(tmp,256,(0,256))
            cdf = hist.cumsum()
            lower = 0
            j = 0
            while cdf[j] < 0.02*cdf[-1]:
                lower += 1
                j += 1
            upper = 255    
            j = 255
            while cdf[j] > 0.98*cdf[-1]:
                upper -= 1
                j -= 1
            if upper==0:
                upper = 255
                print 'Saturated stretch failed'
            fp = (bin_edges-lower)*255/(upper-lower) 
            fp = np.where(bin_edges<=lower,0,fp)
            fp = np.where(bin_edges>=upper,255,fp)
            X[:,i] = np.byte(np.interp(tmp,bin_edges,fp))
            i += 1       
    elif enhance == 'equalization':   
        i = 0
        for tmp in [redband,greenband,blueband]:     
            tmp = tmp.ravel()    
            mx = np.max(tmp)
            mn = np.min(tmp)  
            if mx-mn > 0:
                tmp = (tmp-mn)*255.0/(mx-mn)  
            tmp = np.where(tmp<0,0,tmp)  
            tmp = np.where(tmp>255,255,tmp)  
            hist,bin_edges = np.histogram(tmp,256,(0,256)) 
            cdf = hist.cumsum()
            lut = 255*cdf/float(cdf[-1]) 
            X[:,i] = np.byte(np.interp(tmp,bin_edges[:-1],lut))
            i += 1
    elif enhance == 'logarithmic':   
        i = 0
        for tmp in [redband,greenband,blueband]:     
            tmp = tmp.ravel() 
            mn = np.min(tmp)
            if mn < 0:
                tmp = tmp - mn
            idx = np.where(tmp == 0)
            tmp[idx] = np.mean(tmp)  # get rid of black edges
            idx = np.where(tmp > 0)
            tmp[idx] = np.log(tmp[idx])            
            mn =np.min(tmp)
            mx = np.max(tmp)
            if mx-mn > 0:
                tmp = (tmp-mn)*255.0/(mx-mn)    
            tmp = np.where(tmp<0,0,tmp)  
            tmp = np.where(tmp>255,255,tmp)
#          2% linear stretch           
            hist,bin_edges = np.histogram(tmp,256,(0,256))
            cdf = hist.cumsum()
            lower = 0
            j = 0
            while cdf[j] < 0.02*cdf[-1]:
                lower += 1
                j += 1
            upper = 255    
            j = 255
            while cdf[j] > 0.98*cdf[-1]:
                upper -= 1
                j -= 1
            if upper==0:
                upper = 255
                print 'Saturated stretch failed'
            fp = (bin_edges-lower)*255/(upper-lower) 
            fp = np.where(bin_edges<=lower,0,fp)
            fp = np.where(bin_edges>=upper,255,fp)
            X[:,i] = np.byte(np.interp(tmp,bin_edges,fp))
            i += 1                           
    return np.reshape(X,(rows,cols,3))/255.

def dispms(filename1=None,filename2=None,dims=None,DIMS=None,rgb=None,RGB=None,enhance=None,ENHANCE=None,KLM=None,cls=None,CLS=None,alpha=None):
    gdal.AllRegister()
    if filename1 == None:        
        filename1 = raw_input('Enter image filename: ')
    inDataset1 = gdal.Open(filename1,GA_ReadOnly)    
    projection = inDataset1.GetProjection()
    geotransform = inDataset1.GetGeoTransform() 
    try:                   
        cols = inDataset1.RasterXSize    
        rows = inDataset1.RasterYSize  
        bands1 = inDataset1.RasterCount  
    except Exception as e:
        print 'Error in dispms: %s  --could not read image file'%e
        return   
    if filename2 is not None:                
        inDataset2 = gdal.Open(filename2,GA_ReadOnly) 
        try:       
            cols2 = inDataset2.RasterXSize    
            rows2 = inDataset2.RasterYSize            
            bands2 = inDataset2.RasterCount       
        except Exception as e:
            print 'Error in dispms: %s  --could not read second image file'%e
            return       
    if dims == None:
        dims = [0,0,cols,rows]
    x0,y0,cols,rows = dims
    if rgb == None:
        rgb = [1,1,1]
    r,g,b = rgb
    r = int(np.min([r,bands1]))
    g = int(np.min([g,bands1]))
    b = int(np.min([b,bands1]))
    if enhance == None:
        enhance = 5
    if enhance == 1:
        enhance1 = 'linear255'
    elif enhance == 2:
        enhance1 = 'linear'
    elif enhance == 3:
        enhance1 = 'linear2pc'
    elif enhance == 4:
        enhance1 = 'equalization'
    elif enhance == 5:
        enhance1 = 'logarithmic'    
    else:
        enhance = 'linear2pc' 
    try:  
        if cls is None:
            redband   = np.nan_to_num(inDataset1.GetRasterBand(r).ReadAsArray(x0,y0,cols,rows)) 
            greenband = np.nan_to_num(inDataset1.GetRasterBand(g).ReadAsArray(x0,y0,cols,rows)) 
            blueband  = np.nan_to_num(inDataset1.GetRasterBand(b).ReadAsArray(x0,y0,cols,rows))
        else:
            classimg = inDataset1.GetRasterBand(1).ReadAsArray(x0,y0,cols,rows).ravel()
            lct = len(auxil.ctable)/3
            ctable = np.reshape(auxil.ctable,(lct,3))
            redband = classimg*0
            greenband = classimg*0
            blueband = classimg*0
            for k in cls:
                idx = np.where(classimg==k)
                redband[idx] = ctable[k,0]
                greenband[idx] = ctable[k,1]
                blueband[idx] = ctable[k,2]
            redband = np.reshape(redband,(rows,cols))    
            greenband = np.reshape(greenband,(rows,cols))
            blueband = np.reshape(blueband,(rows,cols))
        inDataset1 = None   
    except  Exception as e:
        print 'Error in dispms: %s'%e  
        return
    X1 = make_image(redband,greenband,blueband,rows,cols,enhance1)
    if filename2 is not None:
        if DIMS == None:      
            DIMS = [0,0,cols2,rows2]
        x0,y0,cols,rows = DIMS
        if RGB == None:
            RGB = rgb
        r,g,b = RGB
        r = int(np.min([r,bands2]))
        g = int(np.min([g,bands2]))
        b = int(np.min([b,bands2]))
        
        enhance = ENHANCE
        if enhance == None:
            enhance = 5
        if enhance == 1:
            enhance2 = 'linear255'
        elif enhance == 2:
            enhance2= 'linear'
        elif enhance == 3:
            enhance2 = 'linear2pc'
        elif enhance == 4:
            enhance2 = 'equalization'
        elif enhance == 5:
            enhance2 = 'logarithmic'    
        else:
            enhance = 'logarithmic'          
        try:  
            if CLS is None:
                redband   = np.nan_to_num(inDataset2.GetRasterBand(r).ReadAsArray(x0,y0,cols,rows))
                greenband = np.nan_to_num(inDataset2.GetRasterBand(g).ReadAsArray(x0,y0,cols,rows)) 
                blueband  = np.nan_to_num(inDataset2.GetRasterBand(b).ReadAsArray(x0,y0,cols,rows))
            else:
                classimg = inDataset2.GetRasterBand(1).ReadAsArray(x0,y0,cols,rows).ravel()
                lct = len(auxil.ctable)/3
                ctable = np.reshape(auxil.ctable,(lct,3))
                redband = classimg*0
                greenband = classimg*0
                blueband = classimg*0
                for k in CLS:
                    idx = np.where(classimg==k)
                    redband[idx] = ctable[k,0]
                    greenband[idx] = ctable[k,1]
                    blueband[idx] = ctable[k,2]
                redband = np.reshape(redband,(rows,cols))    
                greenband = np.reshape(greenband,(rows,cols))
                blueband = np.reshape(blueband,(rows,cols))
            inDataset2 = None   
        except  Exception as e:
            print 'Error in dispms: %s'%e  
            return
        X2 = make_image(redband,greenband,blueband,rows,cols,enhance2)  
        if alpha is not None:
            f, ax = plt.subplots(figsize=(10,10)) 
            ax.imshow(X1)
            ax.imshow(X2,alpha=alpha)
            ax.set_title('%s: %s: %s: %s\n'%(os.path.basename(filename1),enhance1, str(rgb), str(dims)))
        else:    
            f, ax = plt.subplots(1,2,figsize=(20,10))
            ax[0].imshow(X1)
            ax[0].set_title('%s: %s: %s:  %s\n'%(os.path.basename(filename1),enhance1, str(rgb), str(dims)))
            ax[1].imshow(X2)
            ax[1].set_title('%s: %s: %s: %s\n'%(os.path.basename(filename2),enhance2, str(RGB), str(DIMS)))
    else:
        if cls is not None:
            f, ax = plt.subplots(figsize=(15,10))
            cmap = colors.ListedColormap(ctable/255.)
            ticks = range(lct)
            tickspos = map(lambda x: 0.8*x/float(lct),ticks)
            cax = ax.imshow(X1,cmap=cmap)        
            cbar = f.colorbar(cax,ticks=tickspos,orientation='vertical',shrink=0.7)
            cbar.set_ticks(tickspos)
            cbar.set_ticklabels(map(str,ticks))
        else:
            f, ax = plt.subplots(figsize=(10,10))
            ax.imshow(X1) 
        ax.set_title('%s: %s: %s: %s\n'%(os.path.basename(filename1),enhance1, str(rgb), str(dims))) 
    if KLM:
        X1 = np.array(X1*255,dtype=np.uint8)           
        driver = gdal.GetDriverByName( 'GTiff' )
        ds = driver.Create( '/home/tmp.tif', cols, rows, 3, GDT_Byte)           
        for i in range(3):        
            outBand = ds.GetRasterBand(i+1)
            outBand.WriteArray(X1[:,:,i],0,0) 
            outBand.FlushCache() 
#        if projection is not None:
#            ds.SetProjection(projection) 
#        if geotransform is not None:
#            gt = list(geotransform)
#            gt[0] = gt[0] + x0*gt[1]
#            gt[3] = gt[3] + y0*gt[5]
#        ds.SetGeoTransform(tuple(gt))                               
#        "exec    gdalwarp -t_srs:epsg:900913 '/home/tmp.tif' '/home/tmp1.tif' "
#        with open('/home/imagery/overlay_png.kml','w') as f:
#            print >>f, klm('/home/temp1.tif').replace('_image_','overlay.png')           
#            f.close() 
#        os.remove('/home/tmp.tif')    
#        os.remove('/home/tmp1.tif')
            
            
        driver = gdal.GetDriverByName( 'PNG' )
        driver.CreateCopy('/home/imagery/overlay.png', ds, 0)
        os.remove('/home/tmp.tif')            
        with open('/home/imagery/overlay_png.kml','w') as f:
            print >>f, klm(filename1,dims).replace('_image_','overlay.png')           
            f.close()
    plt.show()
                      

def main():
    usage = '''Usage: python %s [-h] [-k] [-c classes] [-C Classes] \n
            [-l] [-L] [-o alpha] \n
            [-e enhancementf] [-E enhancementF]\n
            [-p posf] [P posF [-d dimsf] [-D dimsF]\n
            [-f filename1] [-F filename2] \n
                                        
            if -f is not specified it will be queried\n
            use -c classes and/or -C Classes for classification image\n 
            use -k to generate a PNG of filename1 and associated KLM file to overlay (approximately) on Google Earth\n
            use -o alpha to overlay right onto left image with transparency alpha\n
            RGB bandPositions and spatialDimensions are lists, e.g., -p [1,4,3] -d [0,0,400,400] \n
            enhancements: 1=linear255 2=linear 3=linear2pc 4=equalization 5=logarithmic\n'''%sys.argv[0]
    options,args = getopt.getopt(sys.argv[1:],'hkc:o:C:f:F:p:P:d:D:e:E:')
    filename1 = None
    filename2 = None
    dims = None
    rgb = None
    DIMS = None
    RGB = None
    enhance = None   
    ENHANCE = None
    alpha = None
    cls = None
    CLS = None
    KLM = None
    for option, value in options: 
        if option == '-h':
            print usage
            return 
        elif option == '-k':
            KLM = True
        elif option =='-o':
            alpha = eval(value)
        elif option == '-f':
            filename1 = value
        elif option == '-F':
            filename2 = value    
        elif option == '-p':
            rgb = tuple(eval(value))
        elif option == '-P':
            RGB = tuple(eval(value))    
        elif option == '-d':
            dims = eval(value) 
        elif option == '-D':
            DIMS = eval(value)    
        elif option == '-e':
            enhance = eval(value)  
        elif option == '-E':
            ENHANCE = eval(value)    
        elif option == '-c':
            cls = eval(value)  
        elif option == '-C':
            CLS = eval(value)                
                    
    dispms(filename1,filename2,dims,DIMS,rgb,RGB,enhance,ENHANCE,KLM,cls,CLS,alpha)

if __name__ == '__main__':
    main()