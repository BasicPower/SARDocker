#!/usr/bin/env python
#******************************************************************************
#  Name:     omnibus.py
#  Purpose:  Perform change detection on multi-temporal, polarimetric SAR imagery 
#            Based on Allan Nielsen's Matlab script
#            Condradsen et al. (2015) Accepted for IEEE Transactions on Geoscience and Remote Sensing
#
#  Usage:             
#    python omnibus.py [-d dims] [-s significance] filenamelist enl
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

import numpy as np
from scipy import stats, ndimage
import os, sys, time, getopt, gdal  
from osgeo.gdalconst import GA_ReadOnly, GDT_Float32, GDT_Byte

def getmat(fn,x0,y0,cols,rows,bands):
#  read 9- 4- or 1-band preprocessed files and return real/complex matrix elements 
    inDataset1 = gdal.Open(fn,GA_ReadOnly)     
    if bands == 9:
#      T11 (k1)
        b = inDataset1.GetRasterBand(1)
        k1 = b.ReadAsArray(x0,y0,cols,rows)
#      T12  (a1)
        b = inDataset1.GetRasterBand(2)
        a1 = b.ReadAsArray(x0,y0,cols,rows)
        b = inDataset1.GetRasterBand(3)    
        im = b.ReadAsArray(x0,y0,cols,rows)
        a1 = (a1 + 1j*im)
#      T13  (rho1)
        b = inDataset1.GetRasterBand(4)
        rho1 = b.ReadAsArray(x0,y0,cols,rows)
        b = inDataset1.GetRasterBand(5)
        im = b.ReadAsArray(x0,y0,cols,rows)
        rho1 = (rho1 + 1j*im)      
#      T22 (xsi1)
        b = inDataset1.GetRasterBand(6)
        xsi1 = b.ReadAsArray(x0,y0,cols,rows)    
#      T23 (b1)        
        b = inDataset1.GetRasterBand(7)
        b1 = b.ReadAsArray(x0,y0,cols,rows)
        b = inDataset1.GetRasterBand(8)
        im = b.ReadAsArray(x0,y0,cols,rows)
        b1 = (b1 + 1j*im)      
#      T33 (zeta1)
        b = inDataset1.GetRasterBand(9)
        zeta1 = b.ReadAsArray(x0,y0,cols,rows) 
        inDataset1 = None
        return (k1,a1,rho1,xsi1,b1,zeta1)             
    elif bands == 4:
#      C11 (k1)
        b = inDataset1.GetRasterBand(1)
        k1 = b.ReadAsArray(x0,y0,cols,rows)
#      C12  (a1)
        b = inDataset1.GetRasterBand(2)
        a1 = b.ReadAsArray(x0,y0,cols,rows)
        b = inDataset1.GetRasterBand(3)
        im = b.ReadAsArray(x0,y0,cols,rows)
        a1 = (a1 + 1j*im)        
#      C22 (xsi1)
        b = inDataset1.GetRasterBand(4)
        xsi1 = b.ReadAsArray(x0,y0,cols,rows)  
        inDataset1 = None
        return (k1,a1,xsi1)         
    elif bands == 1:        
#      C11 (k1)
        b = inDataset1.GetRasterBand(1)
        k1 = b.ReadAsArray(x0,y0,cols,rows)  
        inDataset1 = None
        return k1
                       
def main():
    usage = '''
Usage:
------------------------------------------------
    python %s [-h] [-d dims] [-s significance] [-m] infile_1,infile_2,...,infile_n outfilename enl
    
    Perform change detection on multi-temporal, polarimetric SAR imagery in covariance or 
    coherency matrix format.
    
                  infiles are comma-separated, no blank spaces, dims applies to first infile,
                  others are assumed warped to spatial dimension dims
                  outfilename is without path (will be written to same directory as infile_1)
--------------------------------------------'''%sys.argv[0]

    options,args = getopt.getopt(sys.argv[1:],'hmd:s:')
    dims = None
    medianfilter = False
    significance = 0.01
    for option, value in options: 
        if option == '-h':
            print usage
            return 
        elif option == '-m':
            medianfilter = True
        elif option == '-d':
            dims = eval(value)  
        elif option == '-s':
            significance = eval(value)           
    if len(args) != 3:
        print 'Incorrect number of arguments'
        print usage
        sys.exit(1)        
    fns = args[0].split(',')
    outfn = args[1]
    m = np.float64(eval(args[2])) # equivalent number of looks
    n = np.float64(len(fns))      # number of images
    eps = sys.float_info.min
    print '==============================================='
    print 'Multi-temporal Complex Wishart Change Detection'
    print '==============================================='
    print time.asctime()
    gdal.AllRegister()       
#  first SAR image                 
    inDataset1 = gdal.Open(fns[0],GA_ReadOnly)     
    cols = inDataset1.RasterXSize
    rows = inDataset1.RasterYSize    
    bands = inDataset1.RasterCount
    inDataset2 = gdal.Open(fns[1],GA_ReadOnly)  
    if bands==9:       
        p = 3
    elif bands==4:
        p = 2
    elif bands==1:
        p = 1
    else:
        print 'incorrect number of bands'
        return    
    if dims == None:
        dims = [0,0,cols,rows]
    x0,y0,cols,rows = dims 
    print 'first (reference) filename:  %s'%fns[0]
    print 'number of looks: %f'%m 
#  output file
    path = os.path.abspath(fns[0])    
    dirn = os.path.dirname(path)
    outfn = dirn + '/' + outfn 
    start = time.time()
    sumlogdet = 0.0
    k = 0.0; a = 0.0; rho = 0.0; xsi = 0.0; b = 0.0; zeta = 0.0
    for fn in fns:
        print 'ingesting: %s'%fn
        result = getmat(fn,x0,y0,cols,rows,bands)
        if p==3:
            k1,a1,rho1,xsi1,b1,zeta1 = result
            k1 = m*np.float64(k1)
            a1 = m*np.complex128(a1)
            rho1 = m*np.complex128(rho1)
            xsi1 = m*np.float64(xsi1)
            b1 = m*np.complex128(b1)
            zeta1 = m*np.float64(zeta1)
            k += k1; a += a1; rho += rho1; xsi += xsi1; b += b1; zeta += zeta1 
            det1 = k1*xsi1*zeta1 + 2*np.real(a1*b1*np.conj(rho1)) - xsi1*(abs(rho1)**2) - k1*(abs(b1)**2) - zeta1*(abs(a1)**2)  
        elif p==2:
            k1,a1,xsi1 = result
            k1 = m*np.float64(k1)
            a1 = m*np.complex128(a1)
            xsi1 = m*np.float64(xsi1)
            k += k1; a += a1; xsi += xsi1
            det1 = k1*xsi1 - abs(a1)**2
        elif p==1:
            k1 = m*np.float64(result)
            k += k1
            det1 = k1
        x0 = 0 # subsequent files are warped to cols x rows
        y0 = 0           
        idx = np.where(det1 <= 0.0)
        det1[idx] = eps 
        sumlogdet += np.log(det1) 
    if p==3: 
        detsum = k*xsi*zeta + 2*np.real(a*b*np.conj(rho)) - xsi*(abs(rho)**2) - k*(abs(b)**2) - zeta*(abs(a)**2) 
    elif p==2:
        detsum = k*xsi - abs(a)**2
    elif p==1:
        detsum = k  
    idx = np.where(detsum <= 0.0)
    detsum[idx] = eps 
    logdetsum = np.log(detsum)
    lnQ = m*(p*n*np.log(n) + sumlogdet - n*logdetsum)
    f =(n-1)*p**2
    rho = 1 - (2*p**2 - 1)*(n/m - 1/(m*n))/(6*(n - 1)*p)
    omega2 = p**2*(p**2 - 1)*(n/m**2 - 1/(m*n)**2)/(24*rho**2) - p**2*(n - 1)*(1 - 1/rho)**2/4
#  test statistic    
    Z = -2*rho*lnQ
#  change probability
    P =  (1.-omega2)*stats.chi2.cdf(Z,[f])+omega2*stats.chi2.cdf(Z,[f+4])
    if medianfilter:
        P =  ndimage.filters.median_filter(P, size = (3,3))  # for noisy satellite data
#  change map
    a255 = np.ones((rows,cols),dtype=np.byte)*255
    a0 = a255*0
    c11 = np.log(k+0.01) 
    min1 =np.min(c11)
    max1 = np.max(c11)
    c11 = (c11-min1)*255.0/(max1-min1)  
    c11 = np.where(c11<0,a0,c11)  
    c11 = np.where(c11>255,a255,c11) 
    c11 = np.where(P>(1.0-significance),a0,c11)      
    cmap = np.where(P>(1.0-significance),a255,c11)
    cmap0 = np.where(P>(1.0-significance),a255,a0)
#  write to file system        
    driver = inDataset1.GetDriver()  
#    driver = gdal.GetDriverByName('ENVI')  
    outDataset = driver.Create(outfn,cols,rows,3,GDT_Float32)
    geotransform = inDataset2.GetGeoTransform()
    if geotransform is not None:
        outDataset.SetGeoTransform(geotransform)
    projection = inDataset2.GetProjection()        
    if projection is not None:
        outDataset.SetProjection(projection) 
    outBand = outDataset.GetRasterBand(1)
    outBand.WriteArray(Z,0,0) 
    outBand.FlushCache() 
    outBand = outDataset.GetRasterBand(2)
    outBand.WriteArray(P,0,0) 
    outBand.FlushCache() 
    outBand = outDataset.GetRasterBand(3)
    outBand.WriteArray(cmap0,0,0) 
    outBand.FlushCache()     
    outDataset = None
    print 'test statistic, change probabilities and change map written to: %s'%outfn 
    basename = os.path.basename(outfn)
    name, ext = os.path.splitext(basename)
    outfn=outfn.replace(name,name+'_cmap')
    outDataset = driver.Create(outfn,cols,rows,3,GDT_Byte)
    if geotransform is not None:
        outDataset.SetGeoTransform(geotransform)
    projection = inDataset1.GetProjection()        
    if projection is not None:
        outDataset.SetProjection(projection)     
    outBand = outDataset.GetRasterBand(1)
    outBand.WriteArray(cmap,0,0) 
    outBand.FlushCache() 
    outBand = outDataset.GetRasterBand(2)
    outBand.WriteArray(c11,0,0) 
    outBand.FlushCache()  
    outBand = outDataset.GetRasterBand(3)
    outBand.WriteArray(c11,0,0) 
    outBand.FlushCache()  
    outDataset = None    
    inDataset1 = None
    inDataset2 = None
    print 'change map image written to: %s'%outfn  
    print 'elapsed time: '+str(time.time()-start)     
# # test against Matlab   
#     fn = '/home/mort/imagery/sar/emisar/m2rlnQ63646568'
#     inDatasetx = gdal.Open(fn,GA_ReadOnly) 
#     xb = inDatasetx.GetRasterBand(1)
#     Zx = np.transpose(xb.ReadAsArray(0,0,cols,rows))
#     print 'max %.10f'%np.max(Z-Zx)   
#     print 'min %.10f'%np.min(Z-Zx)
#     print 'mean(abs) %.10f'%np.mean(np.abs(Z-Zx))                            
                                    
                
if __name__ == '__main__':
    main()     