# Training a football detection model

The stock detector uses COCO's `sports ball` class: soccer balls,
basketballs, tennis balls. A football is a different shape, usually
partly occluded, often motion-blurred, and frequently the smallest object
in frame. `backend/vision/ball_filter.py` removes the impossible false
positives, but filtering cannot create detections the model never made —
a ball it fails to see is simply missing.

This is what replacing it actually takes.

## Is it worth doing?

Be clear about what improves. Player tracking uses COCO's `person` class,
which the model genuinely knows — that part is already sound and is what
most grading rests on. Ball detection affects ball-distance evidence and
contact geometry.

So: run the pipeline on real film first, look at `rejected_implausible`
in the ball track and how often the ball is found at all, and decide from
that. If the ball is being tracked adequately on your footage, this is
effort better spent elsewhere.

## What it costs

| | |
| --- | --- |
| Labelled frames | 500–2,000 for a usable model |
| Labelling time | 2–6 seconds a frame, so roughly 1–3 hours per 1,000 |
| Training time | 1–3 hours on your GPU |
| Money | £0 with open tools, or ~$20–50/mo for a hosted labeller |

The labelling is the real cost. Everything else is mostly waiting.

## 1. Collect frames

Use your own film — a model trained on the camera angle, distance and
lighting you actually shoot will beat a general one. Pull frames from
clips you have already analysed:

```
python - <<'EOF'
from pathlib import Path
import cv2

src = Path("path/to/game.mp4")
out = Path("dataset/images"); out.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(str(src))
kept = n = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    # Every 15th frame: consecutive frames are nearly identical and add
    # labelling work without adding information.
    if n % 15 == 0:
        cv2.imwrite(str(out / f"{src.stem}-{n:06d}.jpg"), frame)
        kept += 1
    n += 1
cap.release()
print(f"{kept} frames from {n}")
EOF
```

Spread them across several games, both sidelines, and different light
(day, floodlit, overcast). A model trained on one sunny home game will
do poorly on a wet away night.

## 2. Label the ball

Free and local: [labelImg](https://github.com/HumanSignal/labelImg) or
[Label Studio](https://labelstud.io). Hosted and faster:
[Roboflow](https://roboflow.com) — free tier covers a project this size.

Draw one tight box around the ball in every frame where it is visible.
One class, named `football`.

Rules that decide whether this works:

- **Label every visible ball, including partly occluded ones.** Skipping
  the hard cases teaches the model those aren't balls — the exact cases
  you need it to catch.
- **Do not guess.** A frame where you can't actually see the ball gets no
  box. A guessed box is a wrong label, and wrong labels are worse than
  missing ones.
- **Keep frames with no ball visible.** They teach it what isn't a
  football, which is most of what reduces false positives.
- **Box the ball, not the hands around it.**

Export in **YOLO format**. You get an `images/` and `labels/` tree plus a
`data.yaml`.

## 3. Train

On the V2 box, with the GPU already set up:

```
pip install ultralytics
yolo detect train data=dataset/data.yaml model=yolo11s.pt epochs=100 imgsz=1280 batch=8
```

- `yolo11s` over `yolo11n`: the small model detects tiny objects
  meaningfully better, and a football is a tiny object.
- `imgsz=1280` matters more than anything else here. At the default 640 a
  football in a wide shot is a handful of pixels. Raise it further if
  your GPU has the memory.
- Lower `batch` if you hit out-of-memory.

Weights land in `runs/detect/train/weights/best.pt`.

## 4. Check it honestly

Training prints mAP50 on a validation split. Treat that as a starting
signal, not proof: it is measured on frames from the same games, so it
flatters the model. The test that counts is film it has never seen —
ideally a different opponent and different light.

Watch for the failure that matters: a model that finds the ball in easy
frames and misses every contested one scores well and helps nothing,
because contested plays are where grading needs it.

## 5. Use it

```
BALL_MODEL_PATH=/path/to/best.pt
BALL_STRICT_FILTER=false
```

Turn the filter off only once the model is genuinely better — its
heuristics exist to protect against a model that doesn't know what a
football is, and they will also discard correct detections from one that
does. If you are unsure, leave it on: it only ever removes physically
impossible candidates.

Then re-run a clip you have already analysed and compare `rejected_implausible`
and how many frames carry a ball position. That comparison, on your own
film, is the only accuracy number worth acting on.
