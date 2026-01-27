# claude_client.py
import asyncio
from typing import Dict, Any, List, Optional
from anthropic import Anthropic, AsyncAnthropic
from mcp import ClientSession, StdioServerParameters
import json
import os
from dotenv import load_dotenv

load_dotenv()

class DevOpsClaudeClient:
    """Claude SDK client with MCP server integration"""
    
    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.sessions: Dict[str, ClientSession] = {}
        self.available_tools: List[Dict] = []
        
    async def start_mcp_server(self, name: str, command: List[str]):
        """Start an MCP server and connect to it"""
        try:
            session = await ClientSession(
                StdioServerParameters(
                    command=command[0],
                    args=command[1:] if len(command) > 1 else []
                )
            ).__aenter__()
            
            self.sessions[name] = session
            await self._refresh_tools()
            return True
        except Exception as e:
            print(f"Failed to start MCP server {name}: {e}")
            return False
    
    async def _refresh_tools(self):
        """Collect all tools from all connected MCP servers"""
        self.available_tools = []
        
        for name, session in self.sessions.items():
            try:
                tools = await session.list_tools()
                for tool in tools.tools:
                    # Add server name prefix to avoid conflicts
                    tool_dict = tool.model_dump()
                    tool_dict["name"] = f"{name}_{tool.name}"
                    tool_dict["server"] = name
                    self.available_tools.append(tool_dict)
            except Exception as e:
                print(f"Failed to get tools from {name}: {e}")
    
    def _format_tools_for_claude(self) -> List[Dict]:
        """Format MCP tools for Claude API"""
        formatted = []
        for tool in self.available_tools:
            formatted.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", {})
            })
        return formatted
    
    async def analyze_with_tools(self, 
                                 prompt: str, 
                                 max_steps: int = 5,
                                 temperature: float = 0.2) -> Dict[str, Any]:
        """
        Main analysis loop: Claude uses MCP tools to analyze DevOps issues
        """
        messages = [{"role": "user", "content": prompt}]
        step = 0
        results = []
        
        while step < max_steps:
            # Get Claude's response with tool suggestions
            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=temperature,
                tools=self._format_tools_for_claude(),
                messages=messages
            )
            
            # Extract content
            for content in response.content:
                if content.type == "text":
                    results.append({"type": "analysis", "text": content.text})
                    messages.append({
                        "role": "assistant", 
                        "content": content.text
                    })
                
                elif content.type == "tool_use":
                    # Execute the tool
                    tool_name = content.name
                    server_name = tool_name.split("_")[0]
                    actual_tool_name = "_".join(tool_name.split("_")[1:])
                    
                    if server_name in self.sessions:
                        try:
                            # Call the tool via MCP
                            tool_result = await self.sessions[server_name].call_tool(
                                actual_tool_name,
                                content.input
                            )
                            
                            # Add result to conversation
                            result_text = f"Tool {tool_name} result:\n{tool_result}"
                            results.append({
                                "type": "tool_result", 
                                "tool": tool_name,
                                "result": tool_result
                            })
                            
                            messages.append({
                                "role": "user",
                                "content": result_text
                            })
                            
                        except Exception as e:
                            error_msg = f"Tool {tool_name} failed: {str(e)}"
                            results.append({"type": "error", "error": error_msg})
                            messages.append({
                                "role": "user", 
                                "content": error_msg
                            })
            
            step += 1
            
            # Check if Claude is done
            if not any(content.type == "tool_use" for content in response.content):
                break
        
        return {
            "final_analysis": response.content[-1].text if response.content else "",
            "steps": results,
            "tools_used": len([r for r in results if r["type"] == "tool_result"])
        }
    
    async def close(self):
        """Cleanup all MCP sessions"""
        for name, session in self.sessions.items():
            try:
                await session.__aexit__(None, None, None)
            except:
                pass