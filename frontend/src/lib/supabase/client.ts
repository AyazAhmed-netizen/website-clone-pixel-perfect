/**
 * Supabase Client
 *
 * Creates and exports a Supabase client instance for browser use.
 * Note: Requires NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
 * environment variables to be set.
 */

import { createClient as createSupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

let client: ReturnType<typeof createSupabaseClient> | null = null;

/**
 * Create or return existing Supabase client
 */
export function createClient() {
  if (client) return client;

  if (!supabaseUrl || !supabaseAnonKey) {
    // Return a mock client if env vars not set
    console.warn("[Supabase] Missing environment variables, using mock client");
    return {
      auth: {
        getSession: async () => ({ data: { session: null }, error: null }),
        onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
      },
    } as ReturnType<typeof createSupabaseClient>;
  }

  client = createSupabaseClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
  });

  return client;
}

export default createClient;
