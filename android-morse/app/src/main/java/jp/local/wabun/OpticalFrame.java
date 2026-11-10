package jp.local.wabun;

import android.media.Image;
import android.graphics.*;
import java.nio.ByteBuffer;
import java.util.Arrays;

/** Common Y-plane sampling for camera and file decoder. ROI is display-oriented. */
public final class OpticalFrame {
    private final ByteBuffer data;private final int row,pixel,base,rotation;private final Rect crop;
    private final boolean fullRange;
    public OpticalFrame(Image image,int rotation,boolean fullRange){
        Image.Plane p=image.getPlanes()[0];data=p.getBuffer();base=data.position();row=p.getRowStride();pixel=p.getPixelStride();crop=image.getCropRect();this.rotation=((rotation%360)+360)%360;this.fullRange=fullRange;
    }
    private double value(double x,double y){
        double u=x,v=y;if(rotation==90){u=y;v=1-x;}else if(rotation==180){u=1-x;v=1-y;}else if(rotation==270){u=1-y;v=x;}
        int xx=crop.left+Math.max(0,Math.min(crop.width()-1,(int)(u*crop.width()))),yy=crop.top+Math.max(0,Math.min(crop.height()-1,(int)(v*crop.height())));
        int raw=data.get(base+yy*row+xx*pixel)&255;return fullRange?raw:Math.max(0,Math.min(255,(raw-16)*255./219));
    }
    public double[] grid(){double[] a=new double[LightTracker.W*LightTracker.H];for(int y=0;y<LightTracker.H;y++)for(int x=0;x<LightTracker.W;x++)a[y*LightTracker.W+x]=value((x+.5)/LightTracker.W,(y+.5)/LightTracker.H);return a;}
    public double[] features(LightRegion roi){
        double[] center=new double[400],background=new double[1536];int nc=0,nb=0;double sum=0,csum=0;
        roi.aspect=(rotation==90||rotation==270)?crop.height()/(double)crop.width():crop.width()/(double)crop.height();
        double size=roi.width*3.2,cx=roi.x,cy=roi.y;
        // Four subpixel samples approximate area resize of the 128-neighborhood to 64.
        for(int y=0;y<64;y++)for(int x=0;x<64;x++){
            double v=0;for(int sy=0;sy<2;sy++)for(int sx=0;sx<2;sx++)v+=value(cx+((x+.25+sx*.5)/64-.5)*size,cy+((y+.25+sy*.5)/64-.5)*size*roi.aspect);v=Math.rint(v/4);sum+=v;
            if(x>=22&&x<42&&y>=22&&y<42){center[nc++]=v;csum+=v;}if(y<12||y>=52)background[nb++]=v;
        }
        return new double[]{csum/400,OpticalMath.percentile(center,.9),OpticalMath.percentile(background,.5),sum/4096};
    }
    public Bitmap preview(LightRegion roi,LightTracker tracker){
        int w=(rotation==90||rotation==270)?crop.height():crop.width(),h=(rotation==90||rotation==270)?crop.width():crop.height();double scale=320./Math.max(w,h);w=Math.max(1,(int)(w*scale));h=Math.max(1,(int)(h*scale));
        int[] pixels=new int[w*h];for(int y=0;y<h;y++)for(int x=0;x<w;x++){int v=(int)value((x+.5)/w,(y+.5)/h);pixels[y*w+x]=Color.rgb(v,v,v);}
        Bitmap bitmap=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);bitmap.setPixels(pixels,0,w,0,0,w,h);
        return bitmap;
    }
}
