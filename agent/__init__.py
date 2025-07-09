#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF论文分析Agent模块
包含论文总结和问答功能的智能代理
"""

from .paper_summary_agent import PaperSummaryAgent
from .paper_qa_agent import PaperQAAgent

__all__ = ['PaperSummaryAgent', 'PaperQAAgent'] 