#include "auth/key.h"

#if !__has_include("hmac_key.h")
#error "secrets/hmac_key.h yok. Depo kökünde çalıştır: python3 tools/gen_key.py"
#else

#include "hmac_key.h"

#if HMAC_KEY_LEN != FRAME_KEY_BYTES
#error "secrets/hmac_key.h'deki anahtarın uzunluğu FRAME_KEY_BYTES değil"
#endif

const uint8_t auth_key[FRAME_KEY_BYTES] = HMAC_KEY_INIT;

#endif
