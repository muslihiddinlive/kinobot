"""Admin uchun 'Orqaga' tugmasi qayerga qaytishini eslab qoladi.

Ro'yxat sahifasidan (yoki qidiruv natijasidan) foydalanuvchi kartasiga o'tilganda
'Orqaga' aynan o'sha sahifaga qaytishi kerak, 1-sahifaga yoki bosh menyuga emas.
Xotirada saqlanadi (restartdan keyin odatiy 'adm_users' ishlatiladi).
"""
_back: dict[int, str] = {}


def set_back(admin_id: int, callback_data: str) -> None:
    _back[admin_id] = callback_data


def get_back(admin_id: int, default: str = "adm_users") -> str:
    return _back.get(admin_id, default)
