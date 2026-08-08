/**
 * Text filtering utilities for cleaning machine-formatted content
 */

/**
 * Filters out machine-formatted metadata, empty lines, and special characters
 * to keep only human-readable content from action/block messages.
 * 
 * This removes:
 * - Multiple consecutive empty lines (collapsed to single)
 * - Machine metadata patterns (e.g., JSON-like structures, timestamps in machine format)
 * - Special control characters and non-printable characters
 * - Excessive whitespace
 * 
 * @param text - The raw text content to filter
 * @returns Cleaned, human-readable text
 */
export function filterMachineFormattedContent(text: string): string {
  if (!text) return ''
  
  let cleaned = text
  
  // Remove common machine metadata patterns
  // JSON-like structures often used in machine logs
  cleaned = cleaned.replace(/\{[^}]*"timestamp"[^}]*\}\s*/gi, '')
  cleaned = cleaned.replace(/\{[^}]*"meta"[^}]*\}\s*/gi, '')
  cleaned = cleaned.replace(/\{[^}]*"metadata"[^}]*\}\s*/gi, '')
  
  // Remove machine-formatted timestamps (ISO 8601 with milliseconds)
  cleaned = cleaned.replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\s*/g, '')
  
  // Remove UUID patterns
  cleaned = cleaned.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\s*/gi, '')
  
  // Remove common machine prefixes/suffixes
  cleaned = cleaned.replace(/^[\[\{].*?[\]\}]\s*/gm, '')
  // Remove lines that are just JSON-like structures
  cleaned = cleaned.replace(/^\s*[\[\{].*?[\]\}]\s*$/gm, '')
  
  // Remove non-printable control characters (except common whitespace)
  cleaned = cleaned.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
  
  // Remove excessive consecutive whitespace (more than 1 space)
  cleaned = cleaned.replace(/ {2,}/g, ' ')
  
  // Collapse multiple consecutive empty lines to at most 2
  cleaned = cleaned.replace(/\n{4,}/g, '\n\n\n')
  
  // Remove lines that are only machine metadata (contain only special chars/brackets)
  cleaned = cleaned.replace(/^[ \t]*[\[\]\{\}<>()]+[ \t]*$/gm, '')
  
  // Clean up double spaces and trim lines
  cleaned = cleaned.replace(/[ \t]+$/gm, '') // Remove trailing spaces per line
  cleaned = cleaned.replace(/^[ \t]+/gm, '') // Remove leading spaces per line
  
  // Clean up leading/trailing whitespace
  cleaned = cleaned.trim()
  
  return cleaned
}

/**
 * A more aggressive filter for content that appears to be heavily machine-formatted
 * Use this when the standard filter still leaves too much noise
 */
export function aggressiveFilterMachineContent(text: string): string {
  if (!text) return ''
  
  let cleaned = filterMachineFormattedContent(text)
  
  // Remove lines that look like machine headers (all caps with colons)
  cleaned = cleaned.replace(/^[A-Z_]+:\s*$/gm, '')
  
  // Remove lines that are only numbers/special characters
  cleaned = cleaned.replace(/^[0-9\-\_\+\=\*\/\#\$]+$$/gm, '')
  
  // Remove markdown-style code blocks if they don't contain human text
  cleaned = cleaned.replace(/```[\s\S]*?```/g, (match) => {
    // Keep code blocks that contain actual letters/words
    if (/[a-zA-Z]{3,}/.test(match)) return match
    return ''
  })
  
  // Final cleanup of any resulting empty lines
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n')
  
  return cleaned.trim()
}