import wave
import numpy as np
from pydub import AudioSegment
import io
import os
from typing import List, Optional

class AudioProcessor:
    """音频处理工具类"""
    
    def __init__(self, sample_rate: int = 8000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
    
    def create_silence(self, duration_ms: int) -> bytes:
        """创建静音音频数据"""
        # 创建静音数据
        samples = int(self.sample_rate * duration_ms / 1000)
        silence_data = np.zeros(samples, dtype=np.int16)
        
        # 转换为字节
        return silence_data.tobytes()
    
    def merge_audio_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """合并音频数据块"""
        if not audio_chunks:
            return b''
        
        # 合并所有音频数据
        combined_data = b''.join(audio_chunks)
        
        # 确保数据长度是偶数（16位采样）
        if len(combined_data) % 2 != 0:
            combined_data = combined_data[:-1]
        
        return combined_data
    
    def save_as_wav(self, audio_data: bytes, filepath: str, 
                    sample_rate: Optional[int] = None, 
                    channels: Optional[int] = None) -> bool:
        """保存音频数据为WAV文件"""
        try:
            sample_rate = sample_rate or self.sample_rate
            channels = channels or self.channels
            
            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data)
            
            return True
            
        except Exception as e:
            print(f"保存WAV文件失败: {e}")
            return False
    
    def convert_to_mono(self, audio_data: bytes) -> bytes:
        """将立体声音频转换为单声道"""
        try:
            # 将字节数据转换为numpy数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # 如果是立体声，转换为单声道
            if len(audio_array) % 2 == 0:
                # 假设是立体声，取左声道
                mono_array = audio_array[::2]
            else:
                mono_array = audio_array
            
            return mono_array.tobytes()
            
        except Exception as e:
            print(f"转换单声道失败: {e}")
            return audio_data
    
    def normalize_audio(self, audio_data: bytes, target_db: float = -20.0) -> bytes:
        """标准化音频音量"""
        try:
            # 将字节数据转换为numpy数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # 计算当前音量
            current_db = 20 * np.log10(np.mean(np.abs(audio_array)) + 1e-10)
            
            # 计算增益
            gain_db = target_db - current_db
            gain_linear = 10 ** (gain_db / 20)
            
            # 应用增益
            normalized_array = audio_array * gain_linear
            
            # 限制在16位范围内
            normalized_array = np.clip(normalized_array, -32768, 32767)
            
            return normalized_array.astype(np.int16).tobytes()
            
        except Exception as e:
            print(f"标准化音频失败: {e}")
            return audio_data
    
    def create_loop_audio(self, audio_file_path: str, loop_duration_ms: int = 30000) -> bytes:
        """创建循环播放的音频数据"""
        try:
            if not os.path.exists(audio_file_path):
                print(f"音频文件不存在: {audio_file_path}")
                return self.create_silence(loop_duration_ms)
            
            # 加载音频文件
            audio = AudioSegment.from_wav(audio_file_path)
            
            # 如果音频长度小于目标长度，则循环
            if len(audio) < loop_duration_ms:
                loops_needed = int(loop_duration_ms / len(audio)) + 1
                audio = audio * loops_needed
            
            # 截取到目标长度
            audio = audio[:loop_duration_ms]
            
            # 转换为字节
            buffer = io.BytesIO()
            audio.export(buffer, format="wav")
            return buffer.getvalue()
            
        except Exception as e:
            print(f"创建循环音频失败: {e}")
            return self.create_silence(loop_duration_ms)
    
    def add_dtmf_tones(self, audio_data: bytes, dtmf_sequence: str, 
                       tone_duration_ms: int = 100, gap_duration_ms: int = 50) -> bytes:
        """在音频中添加DTMF音调"""
        try:
            # DTMF频率映射
            dtmf_freqs = {
                '1': (697, 1209), '2': (697, 1336), '3': (697, 1477),
                '4': (770, 1209), '5': (770, 1336), '6': (770, 1477),
                '7': (852, 1209), '8': (852, 1336), '9': (852, 1477),
                '*': (941, 1209), '0': (941, 1336), '#': (941, 1477)
            }
            
            # 生成DTMF音调
            dtmf_audio = b''
            for digit in dtmf_sequence:
                if digit in dtmf_freqs:
                    freq1, freq2 = dtmf_freqs[digit]
                    tone = self.generate_dtmf_tone(freq1, freq2, tone_duration_ms)
                    dtmf_audio += tone
                    
                    # 添加间隔
                    if gap_duration_ms > 0:
                        gap = self.create_silence(gap_duration_ms)
                        dtmf_audio += gap
            
            # 合并原始音频和DTMF音调
            return audio_data + dtmf_audio
            
        except Exception as e:
            print(f"添加DTMF音调失败: {e}")
            return audio_data
    
    def generate_dtmf_tone(self, freq1: int, freq2: int, duration_ms: int) -> bytes:
        """生成DTMF双音调"""
        try:
            samples = int(self.sample_rate * duration_ms / 1000)
            t = np.linspace(0, duration_ms / 1000, samples)
            
            # 生成两个频率的正弦波
            wave1 = np.sin(2 * np.pi * freq1 * t)
            wave2 = np.sin(2 * np.pi * freq2 * t)
            
            # 混合两个波形
            mixed_wave = (wave1 + wave2) / 2
            
            # 应用包络（淡入淡出）
            envelope = np.ones(samples)
            fade_samples = int(0.01 * self.sample_rate)  # 10ms淡入淡出
            envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
            envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
            
            # 应用包络并转换为16位整数
            final_wave = mixed_wave * envelope
            final_wave = np.clip(final_wave * 16384, -32768, 32767)
            
            return final_wave.astype(np.int16).tobytes()
            
        except Exception as e:
            print(f"生成DTMF音调失败: {e}")
            return self.create_silence(duration_ms)

# 创建全局音频处理器实例
audio_processor = AudioProcessor()
