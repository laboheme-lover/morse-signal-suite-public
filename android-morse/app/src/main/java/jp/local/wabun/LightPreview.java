package jp.local.wabun;

import android.content.Context;
import android.graphics.*;
import android.view.MotionEvent;
import android.widget.ImageView;

/** Touch coordinates are mapped through FIT_CENTER, including letterbox margins. */
public final class LightPreview extends ImageView {
    public LightRegion region;public volatile double[][] candidates=new double[0][];public Runnable changed;
    private final Paint paint=new Paint();private float initialDistance;private double initialSize;
    public LightPreview(Context c){super(c);setScaleType(ScaleType.FIT_CENTER);setContentDescription("光源プレビュー。タップまたはドラッグで移動、2本指で大きさ変更");}
    private RectF imageRect(){if(getDrawable()==null)return new RectF();RectF r=new RectF(0,0,getDrawable().getIntrinsicWidth(),getDrawable().getIntrinsicHeight());getImageMatrix().mapRect(r);r.offset(getPaddingLeft(),getPaddingTop());return r;}
    @Override protected void onDraw(Canvas c){super.onDraw(c);if(region==null)return;RectF r=imageRect();if(r.isEmpty())return;
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(3);paint.setColor(Color.YELLOW);
        for(double[] p:candidates)c.drawCircle(r.left+(float)p[0]*r.width(),r.top+(float)p[1]*r.height(),10,paint);
        paint.setColor(region.confirmed?Color.GREEN:Color.CYAN);double half=region.width/2;
        c.drawRect(r.left+(float)(region.x-half)*r.width(),r.top+(float)(region.y-half*region.aspect)*r.height(),r.left+(float)(region.x+half)*r.width(),r.top+(float)(region.y+half*region.aspect)*r.height(),paint);
    }
    @Override public boolean onTouchEvent(MotionEvent e){
        if(!isEnabled()||region==null||getDrawable()==null)return false;RectF r=imageRect();
        if(e.getActionMasked()==MotionEvent.ACTION_DOWN&&!r.contains(e.getX(),e.getY()))return false;
        if(e.getActionMasked()==MotionEvent.ACTION_DOWN||e.getActionMasked()==MotionEvent.ACTION_POINTER_DOWN){getParent().requestDisallowInterceptTouchEvent(true);initialDistance=0;}
        if(e.getPointerCount()>=2){float d=(float)Math.hypot(e.getX(1)-e.getX(0),e.getY(1)-e.getY(0));if(initialDistance==0){initialDistance=d;initialSize=region.width;}else region.manual(region.x,region.y,initialSize*d/Math.max(1,initialDistance));}
        else if(e.getActionMasked()==MotionEvent.ACTION_DOWN||e.getActionMasked()==MotionEvent.ACTION_MOVE){
            double x=(e.getX()-r.left)/r.width(),y=(e.getY()-r.top)/r.height(),size=region.width;
            if(e.getActionMasked()==MotionEvent.ACTION_DOWN){double nearest=24;for(double[] p:candidates){double distance=Math.hypot((p[0]-x)*r.width(),(p[1]-y)*r.height());if(distance<nearest){nearest=distance;x=p[0];y=p[1];if(p.length>3)size=p[3];}}}
            region.manual(x,y,size);
        }
        if(e.getActionMasked()==MotionEvent.ACTION_UP){performClick();getParent().requestDisallowInterceptTouchEvent(false);}
        if(changed!=null)changed.run();invalidate();return true;
    }
    @Override public boolean performClick(){super.performClick();return true;}
}
