-- Synthetic component records; no live game memory or captured player data.
local manager, count, index, rows, descriptor, owner = 1000, 1, 0, 2000, 3000, 608
local function global(rva) assert(rva == 0x3326658); return manager end
local function read(address, size) return address end
local function u32(address)
  if address == manager + 0x1c then return count end
  if descriptor and address == descriptor + 8 then return owner end
end
local function pointer(address)
  if address == manager + 0x48 then return rows end
  if rows and address == rows + index * 8 then return descriptor end
end
local function lookup(address, entity)
  assert(address == manager + 0x30)
  if entity == 608 then return index end
end
__EXTRACTION_CLASSIFIER__
assert(not extraction_seat(nil))
assert(not extraction_seat(0))
assert(not extraction_seat(0xffffffff))
for _, entity in ipairs({566, 548, 590}) do assert(not extraction_seat(entity)) end
assert(extraction_seat(608))
owner = 609; assert(not extraction_seat(608)); owner = 608
count = 0; assert(not extraction_seat(608))
count = 65; assert(not extraction_seat(608)); count = 1
index = 1; assert(not extraction_seat(608)); index = 0
rows = nil; assert(not extraction_seat(608)); rows = 2000
descriptor = nil; assert(not extraction_seat(608))
return 'PASS: ordinary vehicles, extraction shuttle and invalid component records'
