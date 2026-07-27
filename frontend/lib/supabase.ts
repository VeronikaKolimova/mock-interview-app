import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://naqsqvbjijhxsotuofmc.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5hcXNxdmJqaWpoeHNvdHVvZm1jIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDU2MjQ4NjQsImV4cCI6MjA2MTIwMDg2NH0.XyFqGzX8K9mLpN3vQ2wR5tY7uA1bC4dE6fG8hI0jK2l';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
