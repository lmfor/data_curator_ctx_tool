import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

def validate_metadata_structure(metadata_path: str = 'hierarchical_output/metadata.json') -> bool:
    """
    Validate that metadata.json has the correct structure for the validation pipeline.
    
    Args:
        metadata_path: Path to the metadata.json file
        
    Returns:
        bool: True if valid, False otherwise
    """
    
    print(f"🔍 Validating metadata file: {metadata_path}")
    
    if not os.path.exists(metadata_path):
        print(f"❌ Metadata file not found: {metadata_path}")
        return False
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"❌ Error loading metadata: {e}")
        return False
    
    if not isinstance(metadata, list):
        print(f"❌ Metadata should be a list, got {type(metadata)}")
        return False
    
    if len(metadata) == 0:
        print(f"⚠️  Metadata is empty")
        return False
    
    print(f"📊 Found {len(metadata)} entries in metadata")
    
    # Required fields for validation pipeline
    required_fields = ['id', 'url', 'title', 'breadcrumbs', 'formatted_date']
    content_fields = ['content', 'markdown_content']  # At least one required
    
    valid_entries = 0
    issues = []
    
    for i, entry in enumerate(metadata):
        entry_issues = []
        
        # Check required fields
        for field in required_fields:
            if field not in entry:
                entry_issues.append(f"Missing required field: {field}")
            elif not entry[field]:  # Check for empty values
                entry_issues.append(f"Empty required field: {field}")
        
        # Check content fields (at least one should exist)
        has_content = any(field in entry and entry[field] for field in content_fields)
        if not has_content:
            entry_issues.append("Missing both 'content' and 'markdown_content'")
        
        # Validate specific field formats
        if 'formatted_date' in entry:
            date_str = entry['formatted_date']
            if not isinstance(date_str, str) or len(date_str.split('/')) != 3:
                entry_issues.append(f"Invalid date format: {date_str} (expected MM/DD/YY)")
        
        if 'url' in entry:
            url = entry['url']
            if not isinstance(url, str) or not url.startswith('http'):
                entry_issues.append(f"Invalid URL format: {url}")
        
        # Count valid entries
        if not entry_issues:
            valid_entries += 1
        else:
            issues.append(f"Entry {i} ({entry.get('title', 'Unknown')}): {', '.join(entry_issues)}")
    
    # Report results
    print(f"✅ Valid entries: {valid_entries}/{len(metadata)}")
    
    if issues:
        print(f"⚠️  Issues found in {len(issues)} entries:")
        for issue in issues[:10]:  # Show first 10 issues
            print(f"   - {issue}")
        if len(issues) > 10:
            print(f"   ... and {len(issues) - 10} more issues")
    
    # Check for markdown content availability
    entries_with_markdown = sum(1 for entry in metadata if entry.get('markdown_content'))
    print(f"📝 Entries with markdown content: {entries_with_markdown}/{len(metadata)}")
    
    if entries_with_markdown == 0:
        print("⚠️  No entries have markdown content - validation pipeline will use HTML")
        print("   Consider running the metadata update script to add markdown content")
    
    # Calculate potential token savings
    if entries_with_markdown > 0:
        total_html_chars = sum(len(entry.get('content', '')) for entry in metadata)
        total_md_chars = sum(len(entry.get('markdown_content', '')) for entry in metadata)
        
        if total_html_chars > 0 and total_md_chars > 0:
            savings = ((total_html_chars - total_md_chars) / total_html_chars) * 100
            print(f"💰 Estimated token savings: {savings:.1f}%")
    
    return valid_entries == len(metadata)

def show_metadata_stats(metadata_path: str = 'hierarchical_output/metadata.json'):
    """Show detailed statistics about the metadata."""
    
    if not os.path.exists(metadata_path):
        print(f"❌ Metadata file not found: {metadata_path}")
        return
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"❌ Error loading metadata: {e}")
        return
    
    print(f"\n📊 Metadata Statistics")
    print("=" * 50)
    
    # Basic stats
    print(f"Total entries: {len(metadata)}")
    
    # Content type distribution
    html_only = sum(1 for entry in metadata if entry.get('content') and not entry.get('markdown_content'))
    markdown_only = sum(1 for entry in metadata if entry.get('markdown_content') and not entry.get('content'))
    both = sum(1 for entry in metadata if entry.get('content') and entry.get('markdown_content'))
    neither = sum(1 for entry in metadata if not entry.get('content') and not entry.get('markdown_content'))
    
    print(f"\nContent distribution:")
    print(f"  HTML only: {html_only}")
    print(f"  Markdown only: {markdown_only}")
    print(f"  Both HTML & Markdown: {both}")
    print(f"  Neither: {neither}")
    
    # Breadcrumb analysis
    breadcrumb_roots = {}
    for entry in metadata:
        breadcrumbs = entry.get('breadcrumbs', '')
        if breadcrumbs:
            root = breadcrumbs.split(' > ')[0] if ' > ' in breadcrumbs else breadcrumbs
            breadcrumb_roots[root] = breadcrumb_roots.get(root, 0) + 1
    
    print(f"\nTop breadcrumb roots:")
    for root, count in sorted(breadcrumb_roots.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {root}: {count} pages")
    
    # Date distribution
    dates = [entry.get('formatted_date', '') for entry in metadata if entry.get('formatted_date')]
    unique_dates = set(dates)
    print(f"\nDate distribution:")
    print(f"  Unique dates: {len(unique_dates)}")
    if unique_dates:
        print(f"  Date range: {min(unique_dates)} to {max(unique_dates)}")
    
    # File size analysis
    if both > 0:
        html_sizes = [len(entry.get('content', '')) for entry in metadata if entry.get('content')]
        md_sizes = [len(entry.get('markdown_content', '')) for entry in metadata if entry.get('markdown_content')]
        
        if html_sizes and md_sizes:
            avg_html_size = sum(html_sizes) / len(html_sizes)
            avg_md_size = sum(md_sizes) / len(md_sizes)
            avg_savings = ((avg_html_size - avg_md_size) / avg_html_size) * 100 if avg_html_size > 0 else 0
            
            print(f"\nAverage content sizes:")
            print(f"  HTML: {avg_html_size:,.0f} characters")
            print(f"  Markdown: {avg_md_size:,.0f} characters")
            print(f"  Average savings: {avg_savings:.1f}%")

def check_pipeline_compatibility(metadata_path: str = 'hierarchical_output/metadata.json'):
    """Check compatibility with the validation pipeline."""
    
    print(f"\n🔧 Pipeline Compatibility Check")
    print("=" * 50)
    
    # Check if metadata exists
    if not os.path.exists(metadata_path):
        print(f"❌ Metadata file not found: {metadata_path}")
        return False
    
    # Check if validation script exists
    validation_script = 'runnables/run_ctx_agent.py'
    if os.path.exists(validation_script):
        print(f"✅ Validation script found: {validation_script}")
    else:
        print(f"⚠️  Validation script not found: {validation_script}")
    
    # Check environment variables
    required_env_vars = ['CONTEXTUAL_API_KEY_PERSONAL', 'CONTEXTUAL_A_ID', 'DATABASE_URL']
    missing_vars = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("   These are required for the validation pipeline")
    else:
        print(f"✅ All required environment variables are set")
    
    # Check database connectivity (if we can import the module)
    try:
        sys.path.insert(0, 'src')
        from db.database import db_manager
        if db_manager.test_connection():
            print(f"✅ Database connection successful")
        else:
            print(f"❌ Database connection failed")
    except Exception as e:
        print(f"⚠️  Could not test database connection: {e}")
    
    print(f"\n🎯 Next steps:")
    print(f"   1. Ensure all environment variables are set")
    print(f"   2. Run: python runnables/run_ctx_agent.py")
    print(f"   3. Monitor the validation progress")

def main():
    print("=" * 60)
    print("Metadata Validation Tool")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        metadata_path = sys.argv[1]
    else:
        metadata_path = 'hierarchical_output/metadata.json'
    
    print(f"Target metadata file: {metadata_path}")
    
    # Validate structure
    is_valid = validate_metadata_structure(metadata_path)
    
    # Show detailed stats
    show_metadata_stats(metadata_path)
    
    # Check pipeline compatibility
    check_pipeline_compatibility(metadata_path)
    
    # Final summary
    print(f"\n" + "=" * 60)
    if is_valid:
        print(f"✅ Metadata is valid and ready for validation pipeline!")
    else:
        print(f"⚠️  Metadata has issues - fix them before running validation pipeline")
    print(f"=" * 60)

if __name__ == "__main__":
    main()