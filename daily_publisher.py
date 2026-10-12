import os
import sys
import json
import random
import re
import urllib.parse
import requests
from upload.upload_facebook import upload_reel, upload_story

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PUBLISHED_FILE = 'published_videos.json'

def load_published():
    if os.path.exists(PUBLISHED_FILE):
        try:
            with open(PUBLISHED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_published(data):
    with open(PUBLISHED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def extract_subject_from_filename(filename):
    name = os.path.splitext(filename)[0]
    name = re.sub(r'_\d{8,}', '', name)
    name = re.sub(r'\d+', '', name)
    name = name.replace('_', ' ').replace('-', ' ').strip()
    name = re.sub(r'^(hydraulic\s+press\s+(crushing|crushes|vs)\s+)', '', name, flags=re.IGNORECASE).strip()
    return name or "fresh juicy fruits"

def clean_caption(text, subject="fruits"):
    if not text:
        return None
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        l = line.strip()
        if re.search(r'^(role\s*:?\s*assistant|reasoning\s*:|thought\s*:|thinking\s*:)', l, re.IGNORECASE):
            continue
        if re.search(r'^(here\s+is|here\'s|as\s+requested|certainly|sure,|note:|\*using\s+key|\*this\s+caption|---)', l, re.IGNORECASE):
            continue
        filtered_lines.append(line)
    text = '\n'.join(filtered_lines)
    text = re.sub(r'\*\*(title|description|caption|hashtags)[^\*]*\*\*[:\s]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(title|description|caption|hashtags)\s*:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'(Support\s+Pollinations|Powered\s+by\s+Pollinations|🌸\s*Ad\s*🌸).*$', '', text, flags=re.IGNORECASE | re.DOTALL).strip()
    text = text.replace('"', '').replace('“', '').replace('”', '').replace('*', '').strip()
    text = re.sub(r'\s+', ' ', text).strip()

    blacklist = [
        'role assistant', 'assistant reasoning', 'reasoning', '<think>',
        'we must produce', 'here is a', 'title:', 'description:',
        'seo optimized', 'social media post', 'char)'
    ]
    lower_text = text.lower()
    for bad in blacklist:
        if bad in lower_text:
            return None

    if len(text) < 25:
        return None

    if len(text) > 280:
        text = text[:280].rsplit(' ', 1)[0]

    return text

def generate_caption(filename=""):
    pollinations_key = os.environ.get('POLLINATIONS_API_KEY', '').strip()
    subject = extract_subject_from_filename(filename) if filename else "fresh fruits"

    if not pollinations_key:
        return get_fallback_caption(subject)

    system_prompt = (
        "You are an expert social media copywriter for viral short-form Facebook Reels. "
        "OUTPUT ONLY the final single-line caption with hashtags. "
        "NEVER output your thoughts, NEVER output reasoning, NEVER output role tags, "
        "and NEVER use labels like Title: or Description:. "
        "Start immediately with an emoji and the hook."
    )
    user_prompt = (
        f"Write a viral, exciting ASMR caption for a 100-ton hydraulic press crushing {subject} "
        f"and extracting extreme satisfying juice with crisp ASMR sound. "
        f"Include high-ranking hashtags (#hydraulicpress #asmr #oddlysatisfying #crush #fruitjuice #satisfying). "
        f"Under 220 characters."
    )

    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(user_prompt)}"
        params = {
            'system': system_prompt,
            'model': 'openai',
            'seed': random.randint(1, 999999)
        }
        headers = {'Authorization': f'Bearer {pollinations_key}'} if pollinations_key else {}
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        if resp.status_code == 200:
            cleaned = clean_caption(resp.text, subject)
            if cleaned:
                return cleaned
            else:
                print(f"  [WARN] Pollinations response contained meta/reasoning or failed validation. Using fallback.")
    except Exception as e:
        print(f"  [WARN] Pollinations caption generation failed: {e}")

    return get_fallback_caption(subject)

def get_fallback_caption(subject="fruits"):
    captions = [
        f"💥 Hydraulic Press vs {subject.title()}! Ultra Satisfying ASMR Juice Extraction 🧃 #hydraulicpress #asmr #satisfying #oddlysatisfying #fruitjuice",
        f"Extreme Pressure vs {subject.title()} 🍉 Watch the satisfying juice burst! #hydraulicpress #asmr #satisfying #crunch #oddlysatisfying",
        f"Crushing {subject.title()} with 100 Tons Hydraulic Press! Most relaxing ASMR crunch 💥 #hydraulicpress #satisfying #asmr #oddlysatisfying",
        f"Satisfying Hydraulic Press vs {subject.title()} 💦 Fresh Juice Burst ASMR #hydraulicpress #crushing #oddlysatisfying #satisfyingvideo",
        f"Watch what happens when 100 TONS crushes {subject.title()}! Pure ASMR crunch 🔊 #hydraulicpress #asmr #satisfying #oddlysatisfying",
        f"Extremely juicy {subject} under the hydraulic press! Oddly satisfying crunch 🍇 #hydraulicpress #asmr #fruitjuice #satisfying",
        f"Ultimate ASMR: Hydraulic Press crushing {subject.title()} into pure juice 🧃💥 #hydraulicpress #satisfying #asmr #oddlysatisfying",
        f"Can {subject.title()} survive 100 Tons of Pressure? Satisfying Juice Burst 💥 #hydraulicpress #satisfying #asmr #fruitcrush"
    ]
    return random.choice(captions)

def generate_pinned_comment(caption):
    custom_link = os.environ.get('PINNED_COMMENT_LINK', '').strip()
    if custom_link:
        link_cta = f"\n\n👉 Full Video & Exclusive Links: {custom_link}"
    else:
        link_cta = "\n\n👉 Follow for daily satisfying ASMR Hydraulic Press juice extractions! 🧃💥"
    return f"{caption}{link_cta}"

def select_video(processed_videos, published):
    published_names = {p.get('filename') for p in published}
    unpublished = [v for v in processed_videos if os.path.basename(v) not in published_names]

    if unpublished:
        return random.choice(unpublished)

    if processed_videos:
        counts = {}
        for p in published:
            name = p.get('filename', '')
            counts[name] = counts.get(name, 0) + 1

        weights = []
        for v in processed_videos:
            name = os.path.basename(v)
            count = counts.get(name, 0)
            weight = max(1, 1000 // (3 ** min(count, 6)))
            weights.append(weight)

        chosen = random.choices(processed_videos, weights=weights, k=1)[0]
        return chosen

    return None

def publish(video_path, publish_to_facebook=True, publish_to_instagram=False):
    filename = os.path.basename(video_path)
    caption = generate_caption(filename)
    pinned_comment = generate_pinned_comment(caption)

    print(f"\n[SEO CAPTION] {caption}")
    print(f"[PINNED COMMENT] {pinned_comment}")

    results = []

    page_id = os.environ.get('FB_PAGE_ID', '1417861724738756').strip()
    page_token = os.environ.get('FB_PAGE_ACCESS_TOKEN', '').strip()
    page_name = "PressView Lens"

    if publish_to_facebook and page_id and page_token:
        print(f"\n--- Publishing to Facebook Page: {page_name} (ID: {page_id}) ---")
        # 1. Reel + Pinned Comment
        reel_res = upload_reel(
            video_path=video_path,
            caption=caption,
            page_id=page_id,
            page_token=page_token,
            pin_comment=True,
            comment_text=pinned_comment
        )
        reel_res['page_name'] = page_name
        results.append(reel_res)

        # 2. Story
        story_res = upload_story(
            video_path=video_path,
            page_id=page_id,
            page_token=page_token
        )
        story_res['page_name'] = page_name
        results.append(story_res)
    elif publish_to_facebook:
        print("[WARN] FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN not set!")

    return results

def run_daily_publish(processed_videos):
    published = load_published()
    video = select_video(processed_videos, published)

    if not video:
        print("[INFO] No videos available to publish")
        return []

    filename = os.path.basename(video)
    print(f"\n[SELECTED VIDEO] {filename}")

    publish_ig = bool(os.environ.get('INSTAGRAM_ACCOUNT_ID'))
    results = publish(video, publish_to_facebook=True, publish_to_instagram=publish_ig)

    entry = {
        'filename': filename,
        'results': results
    }
    published.append(entry)
    save_published(published)

    return results

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    import glob
    processed = glob.glob('Processed_Videos/*.mp4') + glob.glob('Processed_Videos/*.mov')
    results = run_daily_publish(processed)
    print(f"\nPublish results total: {len(results)}")
