#!/usr/bin/env python3
"""
Script to monitor discussion progress
"""
import requests
import time
import json

def monitor_discussion():
    """Monitor the ongoing discussion"""
    try:
        response = requests.get('http://localhost:8000/api/game/state')
        if response.status_code == 200:
            state = response.json()
            
            print(f"Phase: {state.get('phase', 'unknown')}")
            print(f"Day: {state.get('day_number', 0)}")
            
            # Show recent game log
            game_log = state.get('game_log', [])
            if game_log:
                print("\nRecent events:")
                for event in game_log[-5:]:
                    print(f"  {event}")
            
            # Show discussions if any
            discussions = state.get('discussions', [])
            if discussions:
                print(f"\nDiscussions: {len(discussions)} rounds")
                latest = discussions[-1]
                print(f"Latest round: {latest.get('round_number', 'unknown')}")
                print(f"Topic: {latest.get('topic', 'unknown')}")
                messages = latest.get('messages', [])
                print(f"Messages in this round: {len(messages)}")
                
                if messages:
                    print("Recent messages:")
                    for msg in messages[-3:]:
                        print(f"  [{msg.get('sender', 'unknown')}] {msg.get('content', '')[:60]}...")
            
            return state.get('phase')
        else:
            print(f"Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error monitoring: {e}")
        return None

if __name__ == "__main__":
    phase = monitor_discussion()
    print(f"\nCurrent phase: {phase}")