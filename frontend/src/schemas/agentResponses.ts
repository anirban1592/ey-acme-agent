import { z } from 'zod';

// Mirrors backend/agent/response_types.py field-for-field. Keep both sides
// in sync by hand when either changes — there is no codegen between them.

const BaseResponseSchema = z.object({
  request_id: z.string(),
  timestamp: z.string(),
  role_context: z.enum(['sales', 'admin', 'support', 'operations']),
});

const IssueSummarySchema = z.object({
  id: z.number(),
  title: z.string(),
  status: z.string(),
  updated_at: z.string(),
});

const IssueListResponseSchema = BaseResponseSchema.extend({
  type: z.literal('issue_list'),
  customer_name: z.string(),
  issues: z.array(IssueSummarySchema),
});

const CustomerProfileResponseSchema = BaseResponseSchema.extend({
  type: z.literal('customer_profile'),
  customer_name: z.string(),
  fields: z.record(z.string(), z.string().nullable()),
});

const EscalationEmailResponseSchema = BaseResponseSchema.extend({
  type: z.literal('escalation_email'),
  to: z.string(),
  subject: z.string(),
  body: z.string(),
});

const BulletSummaryResponseSchema = BaseResponseSchema.extend({
  type: z.literal('bullet_summary'),
  heading: z.string(),
  points: z.array(z.string()),
});

const ChatMessageResponseSchema = BaseResponseSchema.extend({
  type: z.literal('chat_message'),
  message: z.string(),
});

const ErrorResponseSchema = BaseResponseSchema.extend({
  type: z.literal('error'),
  message: z.string(),
  code: z.string(),
});

export const AgentResponseSchema = z.discriminatedUnion('type', [
  IssueListResponseSchema,
  CustomerProfileResponseSchema,
  EscalationEmailResponseSchema,
  BulletSummaryResponseSchema,
  ChatMessageResponseSchema,
  ErrorResponseSchema,
]);

export type AgentResponse = z.infer<typeof AgentResponseSchema>;
export type IssueListResponse = z.infer<typeof IssueListResponseSchema>;
export type CustomerProfileResponse = z.infer<typeof CustomerProfileResponseSchema>;
export type EscalationEmailResponse = z.infer<typeof EscalationEmailResponseSchema>;
export type BulletSummaryResponse = z.infer<typeof BulletSummaryResponseSchema>;
export type ChatMessageResponse = z.infer<typeof ChatMessageResponseSchema>;
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
