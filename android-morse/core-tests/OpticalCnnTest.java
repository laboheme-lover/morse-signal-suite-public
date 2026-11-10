import jp.local.wabun.*;
import java.io.*;
import java.util.*;

public final class OpticalCnnTest {
 public static void main(String[] args)throws Exception {
  OpticalCnn model=new OpticalCnn(new FileInputStream(args[0]));double worst=0;int matched=0;
  try(DataInputStream in=new DataInputStream(new BufferedInputStream(new FileInputStream(args[1])))){
   int cases=in.readInt();
   for(int k=0;k<cases;k++){
    float[][] x=new float[5][256];for(float[] c:x)for(int i=0;i<c.length;i++)c[i]=in.readFloat();
    float[] actual=model.logits(x),expected=new float[65];int a=0,b=0;
    for(int i=0;i<65;i++){expected[i]=in.readFloat();worst=Math.max(worst,Math.abs(expected[i]-actual[i]));if(actual[i]>actual[a])a=i;if(expected[i]>expected[b])b=i;}
    if(a!=b)throw new AssertionError("Argmax mismatch "+k);matched++;
   }
   int n=in.readInt();double[][] raw=new double[n][4];for(double[] row:raw)for(int j=0;j<4;j++)row[j]=in.readDouble();
   double duration=in.readDouble();float[][] actual=OpticalMath.tensor(raw,duration);
   for(float[] channel:actual)for(float value:channel)if(Math.abs(value-in.readFloat())>2e-5)throw new AssertionError("Tensorization mismatch");
   int count=in.readInt();double[] t=new double[count];double[][] f=new double[count][4];
   for(int i=0;i<count;i++){t[i]=in.readDouble();for(int c=0;c<4;c++)f[i][c]=in.readDouble();}
   double expectedUnit=in.readDouble(),unit=OpticalMath.estimate(t,f);if(Math.abs(unit-expectedUnit)>1e-8)throw new AssertionError("Period mismatch "+unit+" / "+expectedUnit);
   double start=in.readDouble(),end=in.readDouble();float[][] input=OpticalMath.input(t,f,start,end,unit);
   for(float[] channel:input)for(float v:channel)if(Math.abs(v-in.readFloat())>2e-5)throw new AssertionError("Resampling mismatch");
   String expectedText=MorseCodec.hiragana(in.readUTF());
   OpticalReceiver receiver=new OpticalReceiver(model,.3,true);
   for(int i=0;i<t.length;i++)receiver.accept(t[i],f[i]);receiver.finish();
   if(!receiver.text().equals(expectedText))throw new AssertionError("Streaming text "+receiver.text()+" expected "+expectedText);
   int frames=in.readInt();OpticalReceiver video=new OpticalReceiver(model,.3,true);
   for(int i=0;i<frames;i++){double time=in.readDouble();double[] v=new double[4];for(int c=0;c<4;c++)v[c]=in.readDouble();video.accept(time+123456,v);}video.finish();
   String expectedVideo=MorseCodec.hiragana(in.readUTF());if(!video.text().equals(expectedVideo))throw new AssertionError("Recorded crop stream "+video.text()+" / "+expectedVideo);
   System.out.println("PASS decoded six-character video feature replay: "+video.text());
   OpticalReceiver blank=new OpticalReceiver(model,.3,true);for(int i=0;i<500;i++)blank.accept(i/30.,new double[]{10,10,10,10});blank.finish();if(!blank.text().isEmpty())throw new AssertionError("Static light hallucination");
  }
  if(worst>1e-3)throw new AssertionError("Logit difference "+worst);
  SendProgress timeline=new SendProgress(MorseCodec.normalize("いろは が二十□"),.3);
  double total=MorseCodec.encode(timeline.labels).stream().mapToInt(p->p.units).sum()*.3;
  if(Math.abs(total-timeline.total)>1e-8||timeline.active(0)!=-1||timeline.completed(total)!=timeline.ends.length||timeline.active(total)!=-1)throw new AssertionError("Progress boundaries");
  for(int i=0;i<timeline.ends.length;i++)if(timeline.active(timeline.starts[i]+.001)!=i||timeline.completed(timeline.ends[i]+.001)!=i+1)throw new AssertionError("Progress character "+i);
  LightTracker tracker=new LightTracker();LightRegion region=new LightRegion();double[] grid=new double[80*60];
  for(int i=0;i<100;i++){Arrays.fill(grid,10);grid[15*80+15]=240;grid[40*80+50]=(i/10)%2==0?220:10;tracker.update(grid,i/30.,region);}
  if(tracker.candidates.length==0||Math.abs(region.x-50.5/80)>.02)throw new AssertionError("Blink candidate vs static lamp");
  region.confirmed=true;double px=region.x,py=region.y;Arrays.fill(grid,10);for(int i=100;i<120;i++)tracker.update(grid,i/30.,region);
  if(region.x!=px||region.y!=py)throw new AssertionError("Dark tracking drift");
  region.manual(-1,2,4);if(region.confirmed||region.width>.3||region.x<0||region.y>1)throw new AssertionError("ROI bounds");
  boolean rejected=false;try{OpticalMath.estimate(new double[]{0,0},new double[2][4]);}catch(IllegalArgumentException e){rejected=true;}if(!rejected)throw new AssertionError("Bad timing accepted");
  System.out.println("PASS "+matched+" PyTorch/Java predictions; max logit delta="+worst+"; tensor, resampling, timing, send progress, light detection and ROI tests");
 }
}
