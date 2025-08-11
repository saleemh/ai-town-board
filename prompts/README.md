# AI Town Board Prompts

This directory contains external prompt files that can be customized for different analysis tasks.

## Directory Structure

```
prompts/
├── agents/                    # Agent-specific prompts
│   └── meeting_analysis.md   # Meeting analysis agent prompt
└── README.md                 # This file
```

## How It Works

1. **Configuration**: Prompt files are specified in `config/config.yaml` under each agent's configuration
2. **Loading**: Agents automatically load prompts from the specified file path
3. **Fallback**: If a prompt file cannot be found, agents use built-in fallback prompts
4. **Hot Reload**: Changes to prompt files take effect immediately on next analysis run

## Meeting Analysis Prompt

**File**: `agents/meeting_analysis.md`  
**Used by**: MeetingAnalysisAgent  
**Purpose**: Defines the four-section analysis format for agenda items

### Configuration
```yaml
agents:
  meeting_analysis:
    prompt_file: "prompts/agents/meeting_analysis.md"
```

### Format Requirements

The prompt must specify these four sections:
1. **Executive Summary** (< 250 words, standalone)
2. **Topics Included** (Ordered summary, essential points)
3. **Decisions** (Explicit asks, votes, arguments)
4. **Other Takeaways** (All other key information)

## Customization

To customize analysis behavior:

1. **Edit the prompt file** directly (e.g., `prompts/agents/meeting_analysis.md`)
2. **Modify guidelines** to emphasize different aspects
3. **Add special instructions** for specific document types
4. **Test changes** by running analysis on existing meeting data

### Example Customizations

**Focus on Financial Information**:
```markdown
## Special Instructions
- For any item mentioning dollar amounts, always extract the exact cost
- Identify funding sources and budget line items
- Note any financial approvals or expenditure authorizations
```

**Enhanced Decision Tracking**:
```markdown
## Decisions
Record ALL decision points including:
- Formal votes and their outcomes
- Public hearing schedules and requirements  
- Application approvals/denials with reasoning
- Procedural motions and their results
```

## Testing Changes

After modifying a prompt:

```bash
# Test with a single meeting
python -m src analyze --meeting-dir data/meetings/2025-08-13 --force-rebuild

# Check the generated analysis to verify changes took effect
```

## Advanced Configuration

### Multiple Prompt Files
You can create specialized prompts for different scenarios:

```yaml
agents:
  meeting_analysis:
    prompt_file: "prompts/agents/meeting_analysis_detailed.md"
    # Or use different prompts based on meeting type
```

### LLM Parameters
Adjust analysis behavior through config without changing prompts:

```yaml
agents:
  meeting_analysis:
    model: "gpt-4"              # Model selection
    temperature: 0.1            # Consistency (0.0 = very consistent)
    max_tokens: 3000           # Response length limit
    base_url: "custom-api-url"  # Custom LLM endpoint
```

## Best Practices

1. **Test thoroughly** after making prompt changes
2. **Keep backups** of working prompt versions
3. **Document changes** you make to prompts
4. **Start small** with incremental modifications
5. **Use specific examples** in prompts for better results