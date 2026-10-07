#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
#import <ImageIO/ImageIO.h>

static NSArray *pt(VNFaceLandmarkRegion2D *r, VNFaceObservation *f, double W, double H) {
    if (!r || r.pointCount == 0) return nil;
    const CGPoint *p = r.normalizedPoints; double sx=0,sy=0;
    for (NSUInteger i=0;i<r.pointCount;i++){ sx+=(f.boundingBox.origin.x+p[i].x*f.boundingBox.size.width)*W; sy+=(1-(f.boundingBox.origin.y+p[i].y*f.boundingBox.size.height))*H; }
    return @[@(sx/r.pointCount),@(sy/r.pointCount)];
}
static NSArray *extent(VNFaceLandmarkRegion2D *r, VNFaceObservation *f, double W, double H) {
    if (!r || !r.pointCount) return nil; const CGPoint *p=r.normalizedPoints; double x0=DBL_MAX,y0=DBL_MAX,x1=-DBL_MAX,y1=-DBL_MAX;
    for(NSUInteger i=0;i<r.pointCount;i++){double x=(f.boundingBox.origin.x+p[i].x*f.boundingBox.size.width)*W,y=(1-(f.boundingBox.origin.y+p[i].y*f.boundingBox.size.height))*H;x0=fmin(x0,x);x1=fmax(x1,x);y0=fmin(y0,y);y1=fmax(y1,y);}
    return @[@(x1-x0),@(y1-y0)];
}
int main(int argc,const char **argv){ @autoreleasepool {
 if(argc!=3){fprintf(stderr,"usage: detect <photo-dir> <out.json>\n");return 2;}
 NSString *dir=@(argv[1]); NSArray *names=[[[NSFileManager defaultManager] contentsOfDirectoryAtPath:dir error:nil] sortedArrayUsingSelector:@selector(localizedStandardCompare:)]; NSMutableArray *out=[NSMutableArray array]; int n=0,fail=0;
 for(NSString *name in names){NSString *e=name.pathExtension.lowercaseString;if(![@[ @"jpg",@"jpeg",@"png",@"heic" ] containsObject:e])continue;n++;NSString *path=[dir stringByAppendingPathComponent:name];NSURL *url=[NSURL fileURLWithPath:path];CGImageSourceRef src=CGImageSourceCreateWithURL((__bridge CFURLRef)url,NULL);if(!src){[out addObject:@{@"file":name,@"error":@"open"}];fail++;continue;} NSDictionary *props=CFBridgingRelease(CGImageSourceCopyPropertiesAtIndex(src,0,NULL));int ori=[props[(NSString*)kCGImagePropertyOrientation] intValue]?:1;double W=[props[(NSString*)kCGImagePropertyPixelWidth] doubleValue],H=[props[(NSString*)kCGImagePropertyPixelHeight] doubleValue];if(ori>=5&&ori<=8){double q=W;W=H;H=q;}CGImageRef im=CGImageSourceCreateImageAtIndex(src,0,NULL);CFRelease(src);
  VNDetectFaceLandmarksRequest *req=[VNDetectFaceLandmarksRequest new];req.revision=VNDetectFaceLandmarksRequestRevision3;NSError *err=nil;VNImageRequestHandler *h=[[VNImageRequestHandler alloc]initWithCGImage:im orientation:(CGImagePropertyOrientation)ori options:@{}];[h performRequests:@[req] error:&err];CGImageRelease(im);NSArray *faces=req.results;if(err||!faces.count){[out addObject:@{@"file":name,@"error":err.localizedDescription?:@"no face"}];fail++;continue;}VNFaceObservation *f=faces[0];for(VNFaceObservation *q in faces)if(q.boundingBox.size.width*q.boundingBox.size.height>f.boundingBox.size.width*f.boundingBox.size.height)f=q;VNFaceLandmarks2D *l=f.landmarks;NSArray *L=pt(l.leftPupil?:l.leftEye,f,W,H),*R=pt(l.rightPupil?:l.rightEye,f,W,H),*nose=pt(l.nose,f,W,H),*mouth=pt(l.outerLips,f,W,H);if(!L||!R||!nose||!mouth){[out addObject:@{@"file":name,@"error":@"missing landmarks"}];fail++;continue;}if([L[0] doubleValue]>[R[0] doubleValue]){NSArray*q=L;L=R;R=q;}const CGPoint *op=l.outerLips.normalizedPoints;double mlx=DBL_MAX,mrx=-DBL_MAX,mly=0,mry=0;for(NSUInteger i=0;i<l.outerLips.pointCount;i++){double x=(f.boundingBox.origin.x+op[i].x*f.boundingBox.size.width)*W,y=(1-(f.boundingBox.origin.y+op[i].y*f.boundingBox.size.height))*H;if(x<mlx){mlx=x;mly=y;}if(x>mrx){mrx=x;mry=y;}}
  NSMutableDictionary *d=[@{@"file":name,@"w":@(W),@"h":@(H),@"faces":@(faces.count),@"eyeL":L,@"eyeR":R,@"nose":nose,@"mouth":mouth,@"mouthL":@[@(mlx),@(mly)],@"mouthR":@[@(mrx),@(mry)],@"boxW":@(f.boundingBox.size.width*W),@"conf":@(f.confidence),@"eyeBoxL":extent(l.leftEye,f,W,H),@"eyeBoxR":extent(l.rightEye,f,W,H),@"innerLips":extent(l.innerLips,f,W,H)} mutableCopy];if(f.yaw)d[@"yaw"]=f.yaw;if(f.roll)d[@"roll"]=f.roll;if(f.pitch)d[@"pitch"]=f.pitch;[out addObject:d];
 }
 NSData *json=[NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted error:nil];[json writeToFile:@(argv[2]) atomically:YES];printf("photos: %d, failed: %d\n",n,fail);return 0;
}}
