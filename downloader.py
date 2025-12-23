import requests
import os
from tqdm import tqdm
import m3u8
from Crypto.Cipher import AES
import subprocess

def download_file(url, filename, headers=None):
    """
    Downloads a single file (like MP4) with a progress bar.
    """
    response = requests.get(url, headers=headers, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024 # 1 Kibibyte
    
    t = tqdm(total=total_size, unit='iB', unit_scale=True, desc=os.path.basename(filename))
    with open(filename, 'wb') as f:
        for data in response.iter_content(block_size):
            t.update(len(data))
            f.write(data)
    t.close()
    
    if total_size != 0 and t.n != total_size:
        print("ERROR, something went wrong during download")
        return False
    return True

def download_hls(m3u8_url, output_filename, headers=None):
    """
    Downloads an HLS stream (m3u8), decrypts segments, and merges them.
    Note: Requires ffmpeg for merging if using subprocess, or can be done manually.
    """
    playlist = m3u8.load(m3u8_url, headers=headers)
    segments = playlist.segments
    
    # Check for encryption
    key_uri = None
    key_data = None
    if playlist.keys and playlist.keys[0]:
        key_uri = playlist.keys[0].absolute_uri
        key_response = requests.get(key_uri, headers=headers)
        key_data = key_response.content

    temp_dir = "temp_segments"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    segment_files = []
    print(f"Downloading {len(segments)} segments...")
    for i, segment in enumerate(tqdm(segments)):
        seg_url = segment.absolute_uri
        seg_response = requests.get(seg_url, headers=headers)
        seg_data = seg_response.content
        
        # Decrypt if needed
        if key_data:
            iv = segment.key.iv if segment.key.iv else i.to_bytes(16, byteorder='big')
            cipher = AES.new(key_data, AES.MODE_CBC, iv=iv)
            seg_data = cipher.decrypt(seg_data)
            
        seg_filename = os.path.join(temp_dir, f"seg_{i:04d}.ts")
        with open(seg_filename, 'wb') as f:
            f.write(seg_data)
        segment_files.append(seg_filename)

    # Merge segments
    print("Merging segments...")
    with open(output_filename, 'wb') as output_file:
        for seg_file in segment_files:
            with open(seg_file, 'rb') as f:
                output_file.write(f.read())
            os.remove(seg_file)
            
    os.rmdir(temp_dir)
    print(f"Download complete: {output_filename}")
    return True

# Alternative using ffmpeg for HLS if possible (more robust)
def download_with_ffmpeg(url, output_filename, headers=None):
    """
    Uses ffmpeg to download and merge the stream. 
    Headers can be passed to ffmpeg.
    """
    header_str = ""
    if headers:
        for k, v in headers.items():
            header_str += f"{k}: {v}\r\n"
            
    cmd = [
        'ffmpeg',
        '-headers', header_str,
        '-i', url,
        '-c', 'copy',
        output_filename
    ]
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg error: {e}")
        return False
