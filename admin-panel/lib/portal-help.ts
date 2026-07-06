export const PORTAL_PROMPT_HELP: Record<string, { title: string; description: string; help: string; example: string }> = {
  agent_system: {
    title: "Agente",
    description:
      "Define a personalidade e as regras do seu assistente virtual — tom de voz, o que pode ou não responder e como se comportar com clientes.",
    help:
      "Este é o prompt principal. Descreva quem é o bot, o tom (formal, amigável), o que ele vende ou explica e limites (ex.: não inventar preços). O sistema adiciona automaticamente instruções técnicas de formato; escreva em linguagem natural.",
    example:
      "Ex.: «Você é o assistente da Minha Empresa. Responda em português, de forma clara e objetiva. Use apenas informações da base de conhecimento. Se não souber, diga que vai encaminhar para um atendente.»",
  },
  facts_system: {
    title: "Fatos",
    description:
      "Orienta o que o bot deve lembrar sobre cada cliente ao longo da conversa (nome, preferências, pedidos anteriores).",
    help:
      "Usado internamente para extrair fatos úteis das mensagens e guardar na memória do cliente. Normalmente não precisa alterar — deixe o padrão a menos que o administrador oriente.",
    example:
      "Ex.: «Extraia fatos duráveis: nome, cidade, produto de interesse, prazo mencionado. Ignore cumprimentos genéricos.»",
  },
  summarize_system: {
    title: "Resumo",
    description:
      "Define como conversas longas são resumidas para o bot não perder o contexto quando há muitas mensagens.",
    help:
      "Quando a conversa fica extensa, o sistema gera um resumo automático. Ajuste só se quiser um estilo específico de resumo (mais curto, foco em pedidos, etc.).",
    example:
      "Ex.: «Resuma em até 5 frases: motivo do contato, dúvidas principais e próximos passos combinados.»",
  },
};

export const PORTAL_KNOWLEDGE_INTRO = {
  title: "O que é a base de conhecimento?",
  body:
    "São os documentos oficiais da sua empresa que o bot consulta antes de responder. Quanto mais claro e organizado o conteúdo, melhores as respostas.",
  formats: "Formatos aceitos: .md (Markdown) e .txt (texto puro).",
  examples: [
    "FAQ — perguntas frequentes e respostas",
    "Lista de serviços ou produtos",
    "Horário de funcionamento e formas de contato",
    "Políticas (troca, entrega, suporte)",
    "Tabela de preços ou planos (se quiser que o bot cite valores)",
  ],
  tips: [
    "Use títulos e listas — facilita a busca do bot",
    "Um tema por arquivo (ex.: faq.md, servicos.md)",
    "Após upload ou edição, clique em Reindexar para o bot passar a usar o conteúdo novo",
    "Evite informações desatualizadas — o bot confia no que está aqui",
  ],
};

export const PORTAL_DASHBOARD_GUIDE = {
  howItWorks: [
    { label: "Prompts", text: "Defina como o bot fala e se comporta." },
    { label: "Conhecimento", text: "Envie FAQs e materiais que o bot usa para responder." },
    { label: "Atendimento", text: "Mensagens chegam pelo Chatwoot (WhatsApp, Telegram, etc.)." },
    { label: "Humano", text: "Se o cliente pedir atendente, o bot transfere e para de responder." },
  ],
};
