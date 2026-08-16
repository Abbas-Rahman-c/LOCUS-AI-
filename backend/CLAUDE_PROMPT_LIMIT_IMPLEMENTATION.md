# Claude Prompt Limit Per User Implementation

## Overview
This implementation adds a weekly rolling window limit of 250 Claude API prompts per authenticated user. The system tracks usage in the database and enforces limits at the API endpoint level.

## Components Added

### 1. Database Migration
**File**: `backend/src/database/migrations/021_user_prompt_limits.sql`

Creates the `user_limits` table with the following structure:
- `email` (TEXT, PRIMARY KEY part 1): User's email address as identifier
- `limit_type` (TEXT, PRIMARY KEY part 2): Type of limit (e.g., 'claude_weekly_prompts')
- `window_start` (TIMESTAMPTZ): Start of the current 7-day window
- `prompt_count` (INT): Number of prompts used in current window

The table includes indexes for efficient lookups and window-based queries.

### 2. User Limits Service
**File**: `backend/src/modules/ratelimit/user_limits.py`

Core functions:
- `get_user_email_from_id()`: Resolves user email from auth.users table using user_id
- `check_and_increment_prompt_limit()`: Atomic check-and-increment operation with window reset logic
- `get_user_prompt_usage()`: Returns current usage statistics for a user
- `enforce_user_prompt_limit()`: Core enforcement logic that raises HTTP 429 when limit exceeded
- `enforce_user_prompt_limit_dependency()`: FastAPI dependency factory for route integration

Key features:
- **Rolling 7-day window**: Automatically resets when 7 days have elapsed since window_start
- **Atomic operations**: Uses database transactions and row-level locking (FOR UPDATE) to prevent race conditions
- **Detailed error responses**: Includes usage statistics in HTTP headers when limit is exceeded
- **Database-backed**: Persists across server restarts and works in multi-instance deployments

### 3. API Endpoint Integration
The user prompt limit dependency has been added to all Claude API endpoints:

#### Search Endpoint
**File**: `backend/src/modules/search/router.py`
- Added `enforce_user_prompt_limit_dependency()` to `/search` endpoint
- Works alongside existing tenant rate limiting

#### Retrieval Endpoint  
**File**: `backend/src/modules/retrieval/router.py`
- Added `enforce_user_prompt_limit_dependency()` to `/ask` endpoint
- Ensures QA requests are counted against user limit

#### Digest Endpoint
**File**: `backend/src/modules/digest/router.py`
- Added `enforce_user_prompt_limit_dependency()` to `/digest` endpoint
- Applies to both personal and team digest generation

## Configuration

Constants defined in `user_limits.py`:
```python
WEEKLY_PROMPT_LIMIT = 250  # Maximum prompts per 7-day window
WINDOW_DAYS = 7            # Window duration in days
LIMIT_TYPE = "claude_weekly_prompts"  # Identifier for this limit type
```

## Behavior

### Normal Operation
1. User makes authenticated request to Claude-powered endpoint
2. System extracts user_id from JWT token
3. Looks up user email from auth.users table
4. Checks user_limits table for current usage
5. If within limit: increments counter and processes request
6. If limit exceeded: returns HTTP 429 with detailed error

### Window Reset Logic
- If `now >= window_start + 7 days`, the window is reset
- Counter set to 1 (for current request)
- New window_start set to current time
- User gets fresh 250-prompt allowance

### Limit Exceeded Response
When limit is exceeded, returns HTTP 429 with:
```json
{
  "detail": "Weekly prompt limit exceeded (250/250). Window resets on 2026-08-22 14:30:00 UTC."
}
```

Headers included:
- `Retry-After`: Seconds until window reset
- `X-PromptLimit`: The limit (250)
- `X-PromptUsed`: Current usage count
- `X-PromptRemaining`: Remaining prompts (0)
- `X-WindowReset`: ISO timestamp of window reset

## Deployment Steps

1. **Run Database Migration**
   ```bash
   # Apply the migration to create the user_limits table
   # This will depend on your specific migration deployment process
   ```

2. **Deploy Backend Code**
   - The new files are already in place
   - No configuration changes needed
   - Endpoints will automatically enforce limits after deployment

3. **Verification**
   - Monitor logs for "Created new limit record for user" messages
   - Check that HTTP 429 responses are returned when limits exceeded
   - Verify window resets work correctly after 7 days

## Testing

### Manual Testing
1. Make authenticated requests to `/search`, `/ask`, or `/digest`
2. Check that requests succeed under the limit
3. Monitor the user_limits table for incrementing counters
4. Verify that after 250 requests, subsequent requests return HTTP 429
5. Wait for window reset (or manually update window_start in DB) and verify requests work again

### Test Script
A basic test script is provided at `backend/src/modules/ratelimit/test_user_limits.py` that validates the core logic without requiring a database connection.

## Security Considerations

- **Authentication Required**: Limits only apply to authenticated users (JWT verification required)
- **User Isolation**: Each user tracked independently by email
- **Race Condition Prevention**: Database transactions and row-level locking prevent concurrent requests from bypassing limits
- **No Information Leakage**: Error messages don't expose other users' usage data

## Future Enhancements

Potential improvements for production:
1. **Admin API**: Add endpoint for admins to view/reset user limits
2. **Usage Dashboard**: Frontend display of current usage for users
3. **Tiered Limits**: Different limits for different subscription tiers
4. **Graceful Degradation**: Queue requests instead of hard blocking when limit exceeded
5. **Notifications**: Alert users when approaching limit

## Rollback Plan

If issues arise:
1. Remove the `enforce_user_prompt_limit_dependency()` calls from routers
2. Comment out or remove the user_limits import statements
3. The database migration can be reverted if needed
4. Existing rate limiting (per-tenant) remains in place as a fallback

## Monitoring

Key metrics to monitor:
- Rate of HTTP 429 responses (indicates limits being hit)
- Growth rate of user_limits table
- Distribution of usage across users
- Time to window reset for blocked users
