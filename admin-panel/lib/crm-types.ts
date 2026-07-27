export type CustomField = {
  id: number;
  key: string;
  label: string;
  field_type: string;
  required: boolean;
  sort_order: number;
};

export type Contact = {
  id: number;
  phone: string;
  name: string;
  email: string;
  fields: Record<string, unknown>;
  chatwoot_contact_id?: number | null;
  last_conversation_id?: number | null;
  updated_at?: string | null;
};

export type InboundWebhook = {
  id: number;
  name: string;
  slug: string;
  secret: string;
  field_mapping: Record<string, string>;
  start_conversation: boolean;
  initial_message: string;
  active: boolean;
  url: string;
  url_path: string;
};

export type HttpTool = {
  id: number;
  name: string;
  slug: string;
  method: string;
  url: string;
  headers: Record<string, string>;
  body_template: string;
  include_fields: string[];
  auth_header: string;
  description: string;
  active: boolean;
};

export type SendableFile = {
  id: number;
  filename: string;
  original_name: string;
  description: string;
  mime_type: string;
  size_bytes: number;
};
