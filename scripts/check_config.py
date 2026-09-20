from app.core.config import get_settings
s = get_settings()
print('Configuration loaded')
print('creator:', s.x_creator_username)
print('entry:', s.fpl_entry_id)
print('auto_transfer:', s.auto_transfer)
print('model:', s.openai_model)
