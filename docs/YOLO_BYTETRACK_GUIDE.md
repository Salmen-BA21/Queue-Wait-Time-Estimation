# YOLO and ByteTrack Guide

This guide explains the two computer-vision pieces used in the backend:

- YOLO detects people in each video frame.
- ByteTrack keeps the same person identified across frames.

Together, they let the system answer not only "how many people are here now?" but also "who entered, who left, and how long did they stay?"

## 1) YOLO: What It Does

YOLO is the detection model. It looks at one frame and returns bounding boxes around objects it recognizes. In this project, it is used only for the `person` class.

In the backend, YOLO is loaded in [backend/src/detector.py](../backend/src/detector.py) and called once per processed frame.

### Default YOLO settings in this project

- Model size: `n`
- Weight file: `yolo26n.pt`
- Confidence threshold: `0.30`
- Input image size: `512`
- Device: `auto`
- Class filter: `person` only, COCO class id `0`

### What each YOLO setting means

- Model size `n`: the smallest default YOLO model. It is faster and lighter, which is useful for real-time video.
- Confidence `0.30`: YOLO keeps detections only when it is at least 30% confident. Lower values detect more people but may add false positives.
- Image size `512`: the frame is resized to this inference size before detection. Bigger sizes can improve accuracy but are slower.
- Device `auto`: the backend uses GPU if available, otherwise MPS on supported Apple hardware, otherwise CPU.
- Person-only filter: the system ignores cars, chairs, bags, and other objects because the queue logic only needs people.

### YOLO mental model

Think of YOLO as the "eyes" of the system.

It answers:

- Where are the people in this frame?
- How confident am I about each detection?

It does not know whether two detections in two different frames are the same person. That is the job of ByteTrack.

## 2) ByteTrack: What It Does

ByteTrack is the tracker. It takes YOLO detections and tries to keep a stable ID for each person across frames.

In the backend, the wrapper is in [backend/src/tracker.py](../backend/src/tracker.py). The queue analyzer then uses those IDs in [backend/src/queue_analyzer.py](../backend/src/queue_analyzer.py).

### Default ByteTrack settings in this project

- Tracking threshold: `0.25`
- Lost track buffer: `60` frames
- Matching threshold: `0.8`
- Frame rate: taken from the current video source

### What each ByteTrack setting means

- Tracking threshold `0.25`: a detection needs enough confidence before ByteTrack starts a new track for it.
- Lost track buffer `60`: if a person disappears for a short time, ByteTrack keeps the ID alive for 60 frames before dropping it.
- Matching threshold `0.8`: controls how strict the matching is when ByteTrack decides whether a new detection belongs to an existing person.
- Frame rate: helps ByteTrack interpret how long a track should remain alive and how tracking behaves over time.

### ByteTrack mental model

Think of ByteTrack as the system's "memory".

It answers:

- Is this the same person as before?
- Did this person leave the zone?
- Did a new person enter the zone?

Without tracking IDs, the system would only know occupancy at each frame. With tracking IDs, it can detect arrivals and departures.

## 3) Why Both Are Needed

YOLO alone gives detection, but detection alone is not enough for queue analytics.

ByteTrack makes the detections useful for:

- counting arrivals,
- counting departures,
- estimating service rate,
- estimating wait time,
- handling short occlusions when people cross each other.

That is why the project uses YOLO first and ByteTrack after it.

## 4) How the Pipeline Works

1. Read one video frame.
2. Run YOLO to find people.
3. Pass detections to ByteTrack.
4. ByteTrack assigns or updates `tracker_id` values.
5. The queue analyzer compares current IDs with previous IDs.
6. If an ID is new, it counts as an arrival.
7. If an old ID disappears, it counts as a departure.
8. The backend estimates queue metrics from those events.

## 5) Simple Example

Suppose three people are visible in the zone.

### With YOLO only

- Frame 1: 3 people
- Frame 2: 3 people
- Frame 3: 3 people

You still only know occupancy.

### With YOLO + ByteTrack

- Frame 1: IDs `1, 2, 3`
- Frame 2: IDs `1, 2, 3`
- Frame 3: IDs `1, 2, 4`

Now the system knows:

- person `4` is new,
- one tracked person left,
- queue events changed over time.

That is much more useful for wait-time estimation.

## 6) Practical Tuning Notes

If you need fewer false detections, increase YOLO confidence slightly.

If you miss people in difficult lighting or RTSP video, lower YOLO confidence a bit.

If people disappear too quickly when they are briefly occluded, increase ByteTrack lost track buffer.

If different people get merged too easily, review the matching threshold and detection quality.

## 7) Short Summary

- YOLO finds people.
- ByteTrack keeps identity across frames.
- YOLO answers "what is visible now?"
- ByteTrack answers "who is still the same person?"
- The queue analyzer needs both to estimate arrivals, departures, and wait time.
