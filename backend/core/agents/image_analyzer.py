"""
Image Analyzer Agent

Analyzes dashboard screenshots using GPT-4o Vision.
Extracts metric names, values, anomalies, and temporal patterns.

Usage:
    from agents.image_analyzer import analyze_dashboards
    
    evidence = analyze_dashboards(
        images=["path/to/grafana.png"],
        time_window="14:20-14:45"
    )
"""

import base64
import json
import sys
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

import config
from prompts.image import IMAGE_AGENT_PROMPT
from agents.verifier import Evidence


class ImageAnalyzer:
    """
    Analyzes monitoring dashboard screenshots using vision models.
    """
    
    def __init__(self, vision_client=None):
        """
        Initialize image analyzer.
        
        Args:
            vision_client: Optional OpenAI client for vision
        """
        self.vision_client = vision_client
        
        if self.vision_client is None:
            if config.OPENAI_API_KEY and OPENAI_AVAILABLE:
                self.vision_client = OpenAI(api_key=config.OPENAI_API_KEY)
                self.vision_type = "openai"
            elif config.ANTHROPIC_API_KEY and ANTHROPIC_AVAILABLE:
                self.vision_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
                self.vision_type = "anthropic"
            else:
                print("⚠️  No vision API available. Using mock analysis.")
                self.vision_type = "mock"
    
    def analyze_dashboards(
        self,
        images: List[str],
        time_window: Optional[str] = None
    ) -> List[Evidence]:
        """
        Analyzes dashboard screenshots.
        
        Args:
            images: List of image paths or base64 strings
            time_window: Expected time window for metrics
        
        Returns:
            List of Evidence objects with metric observations
        """
        if not images:
            return []
        
        evidence = []
        
        for image_path in images:
            if self.vision_type == "openai":
                image_evidence = self._analyze_with_openai(image_path, time_window)
            elif self.vision_type == "anthropic":
                image_evidence = self._analyze_with_anthropic(image_path, time_window)
            else:
                image_evidence = self._mock_analysis(image_path, time_window)
            
            evidence.extend(image_evidence)
        
        return evidence
    
    def _analyze_with_openai(
        self,
        image_path: str,
        time_window: Optional[str]
    ) -> List[Evidence]:
        """Use GPT-4o Vision to analyze dashboard"""
        
        try:
            # Encode image
            image_data = self._encode_image(image_path)
            
            # Build prompt
            prompt = IMAGE_AGENT_PROMPT
            if time_window:
                prompt += f"\n\nExpected time window: {time_window}"
            
            # Call GPT-4o Vision
            response = self.vision_client.chat.completions.create(
                model=config.VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            return self._parse_vision_response(response_text, image_path)
        
        except Exception as e:
            print(f"⚠️  Vision analysis failed: {e}")
            return self._mock_analysis(image_path, time_window)
    
    def _analyze_with_anthropic(
        self,
        image_path: str,
        time_window: Optional[str]
    ) -> List[Evidence]:
        """Use Claude with vision to analyze dashboard"""
        
        try:
            # Encode image
            image_data = self._encode_image(image_path)
            
            # Determine media type
            media_type = "image/png"
            if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
                media_type = "image/jpeg"
            
            # Build prompt
            prompt = IMAGE_AGENT_PROMPT
            if time_window:
                prompt += f"\n\nExpected time window: {time_window}"
            
            # Call Claude with vision
            response = self.vision_client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Latest vision model
                max_tokens=1500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            # Parse response
            response_text = response.content[0].text
            return self._parse_vision_response(response_text, image_path)
        
        except Exception as e:
            print(f"⚠️  Claude vision analysis failed: {e}")
            return self._mock_analysis(image_path, time_window)
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except FileNotFoundError:
            raise FileNotFoundError(f"Image not found: {image_path}")
    
    def _parse_vision_response(
        self,
        response_text: str,
        image_path: str
    ) -> List[Evidence]:
        """Parse vision model response into Evidence objects"""
        
        try:
            # Remove markdown code blocks if present
            cleaned = response_text.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]
            
            data = json.loads(cleaned.strip())
            
            evidence = []
            
            # Extract metrics
            for metric in data.get("metrics_observed", []):
                content = self._format_metric_observation(metric)
                
                evidence.append(Evidence(
                    source="image",
                    content=content,
                    timestamp=metric.get("time_range", ""),
                    confidence=metric.get("confidence", 0.8),
                    metadata={
                        "metric_name": metric.get("metric_name"),
                        "pattern": metric.get("pattern"),
                        "baseline": metric.get("baseline"),
                        "anomaly_value": metric.get("anomaly_value"),
                        "image_path": image_path
                    }
                ))
            
            # Extract visual anomalies
            for anomaly in data.get("visual_anomalies", []):
                evidence.append(Evidence(
                    source="image",
                    content=f"Visual anomaly: {anomaly}",
                    timestamp="",
                    confidence=0.7,
                    metadata={"type": "visual_anomaly", "image_path": image_path}
                ))
            
            return evidence
        
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse vision response: {e}")
            print(f"Response: {response_text[:200]}...")
            
            # Fallback: extract information from text
            return self._extract_from_text(response_text, image_path)
    
    def _format_metric_observation(self, metric: dict) -> str:
        """Format metric observation for display"""
        parts = []
        
        metric_name = metric.get("metric_name", "Unknown metric")
        pattern = metric.get("pattern", "anomaly")
        
        parts.append(f"{metric_name} showed {pattern}")
        
        if metric.get("baseline") and metric.get("anomaly_value"):
            parts.append(f"from {metric['baseline']} to {metric['anomaly_value']}")
        
        if metric.get("time_range"):
            parts.append(f"at {metric['time_range']}")
        
        return " ".join(parts)
    
    def _extract_from_text(
        self,
        text: str,
        image_path: str
    ) -> List[Evidence]:
        """Extract information from free-form text response"""
        evidence = []
        
        # Look for common patterns
        text_lower = text.lower()
        
        if "cpu" in text_lower and any(w in text_lower for w in ["spike", "high", "increase"]):
            evidence.append(Evidence(
                source="image",
                content="CPU usage showed spike (extracted from description)",
                timestamp="",
                confidence=0.6,
                metadata={"image_path": image_path, "extraction": "text"}
            ))
        
        if "memory" in text_lower and any(w in text_lower for w in ["high", "increase", "leak"]):
            evidence.append(Evidence(
                source="image",
                content="Memory usage increase detected (extracted from description)",
                timestamp="",
                confidence=0.6,
                metadata={"image_path": image_path, "extraction": "text"}
            ))
        
        if "error" in text_lower or "alert" in text_lower:
            evidence.append(Evidence(
                source="image",
                content="Error indicators visible in dashboard",
                timestamp="",
                confidence=0.7,
                metadata={"image_path": image_path, "extraction": "text"}
            ))
        
        return evidence
    
    def _mock_analysis(
        self,
        image_path: str,
        time_window: Optional[str]
    ) -> List[Evidence]:
        """Mock analysis when vision API unavailable"""
        
        print(f"ℹ️  Using mock analysis for {image_path}")
        
        # Return plausible mock observations
        evidence = [
            Evidence(
                source="image",
                content="CPU usage spike detected (mock observation)",
                timestamp=time_window.split('-')[0] if time_window else "unknown",
                confidence=0.5,
                metadata={
                    "mock": True,
                    "image_path": image_path,
                    "note": "Vision API not available - mock data"
                }
            ),
            Evidence(
                source="image",
                content="Error rate increase visible (mock observation)",
                timestamp=time_window.split('-')[0] if time_window else "unknown",
                confidence=0.5,
                metadata={
                    "mock": True,
                    "image_path": image_path,
                    "note": "Vision API not available - mock data"
                }
            )
        ]
        
        return evidence


# Module-level convenience function
_analyzer_instance = None

def get_analyzer() -> ImageAnalyzer:
    """Get or create singleton analyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ImageAnalyzer()
    return _analyzer_instance


def analyze_dashboards(
    images: List[str],
    time_window: Optional[str] = None
) -> List[Evidence]:
    """
    Convenience function for analyzing dashboards.
    
    Args:
        images: List of image paths
        time_window: Optional time window
    
    Returns:
        List of Evidence objects
    """
    analyzer = get_analyzer()
    return analyzer.analyze_dashboards(images, time_window)


# CLI for testing
def main():
    """Test image analysis"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test dashboard image analysis")
    parser.add_argument('images', nargs='+', help='Dashboard image paths')
    parser.add_argument('--time-window', help='Time window (HH:MM-HH:MM)')
    
    args = parser.parse_args()
    
    print("="*60)
    print("IMAGE ANALYSIS TEST")
    print("="*60)
    print(f"Images: {args.images}")
    print(f"Time window: {args.time_window or 'None'}")
    print("="*60)
    
    # Analyze images
    evidence = analyze_dashboards(args.images, args.time_window)
    
    print(f"\nExtracted {len(evidence)} observations:\n")
    
    for i, ev in enumerate(evidence, 1):
        print(f"{i}. (confidence: {ev.confidence:.2f})")
        print(f"   {ev.content}")
        
        if ev.metadata.get("mock"):
            print(f"   ⚠️  {ev.metadata['note']}")
        
        print()
    
    print("="*60)


if __name__ == "__main__":
    main()