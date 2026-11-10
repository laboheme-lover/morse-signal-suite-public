package jp.local.wabun;

import java.util.*;

/** Temporal range proposes blinking sources; a steady bright lamp is not enough.
 * Tracking is local and only updates during bright frames. No jump across scene. */
public final class LightTracker {
    public static final int W=80,H=60;
    private final double[] low=new double[W*H],high=new double[W*H],prev=new double[W*H];
    private final int[] changes=new int[W*H];
    private int frames;private double started=-1;
    public double[][] candidates=new double[0][];
    public String status="点滅する光源を探しています";
    public void update(double[] grid,double time,LightRegion roi){
        if(started<0||time-started>15){started=time;frames=0;Arrays.fill(changes,0);}
        for(int i=0;i<grid.length;i++){
            if(frames==0)low[i]=high[i]=grid[i];else {low[i]=Math.min(grid[i],low[i]+.1);high[i]=Math.max(grid[i],high[i]-.1);if(Math.abs(grid[i]-prev[i])>20)changes[i]++;}prev[i]=grid[i];
        }frames++;
        if(frames%5!=0)return;
        List<double[]> found=new ArrayList<>();boolean[] used=new boolean[W*H];
        for(int k=0;k<3;k++){
            double best=20;int pos=-1;
            for(int y=4;y<H-4;y++)for(int x=4;x<W-4;x++){int i=y*W+x;double score=(high[i]-low[i])*Math.min(3,changes[i])/3.;if(!used[i]&&changes[i]>=2&&score>best){best=score;pos=i;}}
            if(pos<0)break;int px=pos%W,py=pos/W;
            ArrayDeque<Integer> queue=new ArrayDeque<>();queue.add(pos);used[pos]=true;int minx=px,maxx=px,miny=py,maxy=py,count=0;double sumx=0,sumy=0;
            while(!queue.isEmpty()){
                int at=queue.remove(),x=at%W,y=at/W;count++;sumx+=x+.5;sumy+=y+.5;
                minx=Math.min(minx,x);maxx=Math.max(maxx,x);miny=Math.min(miny,y);maxy=Math.max(maxy,y);
                for(int next:new int[]{at-1,at+1,at-W,at+W})if(next>=0&&next<W*H&&!used[next]&&Math.abs(next%W-x)+Math.abs(next/W-y)==1&&changes[next]>=2&&(high[next]-low[next])>=best*.5){used[next]=true;queue.add(next);}
            }
            if(count<W*H/5){double width=Math.max((maxx-minx+1.)/W,(maxy-miny+1.)/H/roi.aspect)*1.15;found.add(new double[]{sumx/count/W,sumy/count/H,best,Math.max(.02,Math.min(.3,width))});}
            for(int y=Math.max(0,miny-2);y<Math.min(H,maxy+3);y++)for(int x=Math.max(0,minx-2);x<Math.min(W,maxx+3);x++)used[y*W+x]=true;
        }
        candidates=found.toArray(new double[0][]);
        if(!roi.confirmed){
            status=found.isEmpty()?"点滅候補なし：送信側を点滅させるか、手動で枠を指定":"候補をタップして緑枠を確認してください";
            if(roi.automatic&&!found.isEmpty())roi.set(found.get(0)[0],found.get(0)[1],found.get(0)[3]);
        }else if(roi.tracking){
            double best=0,bx=roi.x,by=roi.y;
            for(int y=2;y<H-2;y++)for(int x=2;x<W-2;x++){
                double nx=(x+.5)/W,ny=(y+.5)/H;if(Math.abs(nx-roi.x)>roi.width*.6||Math.abs(ny-roi.y)>roi.width*.6)continue;
                int i=y*W+x;double score=grid[i]-low[i];if(score>best){best=score;bx=nx;by=ny;}
            }
            if(best>25){
                double sx=0,sy=0,n=0;
                for(int y=0;y<H;y++)for(int x=0;x<W;x++)if(Math.abs((x+.5)/W-roi.x)<=roi.width*.6&&Math.abs((y+.5)/H-roi.y)<=roi.width*.6*roi.aspect&&grid[y*W+x]-low[y*W+x]>best*.5){sx+=(x+.5)/W;sy+=(y+.5)/H;n++;}
                if(n>0){bx=sx/n;by=sy/n;}roi.x=.85*roi.x+.15*bx;roi.y=.85*roi.y+.15*by;status="光源を局所追跡中";
            }
            else status="消灯中または光源未検出：枠を維持";
        }
    }
}
