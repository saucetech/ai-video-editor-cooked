-- Resolve Console helper. Fixed vendor methods over a private local file mailbox.
-- No network listener, shell execution, source evaluation or request-selected file IO.
local root = __RUNTIME__
assert(ffi and ffi.os == 'OSX', 'This Lua transport currently supports macOS only')
ffi.cdef[[
int open(const char *, int, ...); long read(int, void *, unsigned long);
long write(int, const void *, unsigned long); int close(int);
int rename(const char *, const char *); int chmod(const char *, unsigned short);
typedef struct { long tv_sec; int tv_usec; } cooked_timeval;
int gettimeofday(cooked_timeval *, void *);
]]
local C, null = ffi.C, {}
local function clock()
  local t=ffi.new('cooked_timeval[1]'); assert(C.gettimeofday(t,nil)==0)
  return tonumber(t[0].tv_sec) + tonumber(t[0].tv_usec)/1000000
end
local function readfile(name)
  local fd = C.open(root .. '/' .. name, 0)
  if fd < 0 then return nil end
  local b = ffi.new('char[1048577]'); local n = C.read(fd, b, 1048577); C.close(fd)
  if n < 0 or n > 1048576 then return nil end
  return ffi.string(b, n)
end
local function writefile(name, data)
  local path = root .. '/' .. name
  local fd = C.open(path .. '.tmp', 1 + 512 + 1024, ffi.cast('int', 384)) -- Darwin WRONLY|CREAT|TRUNC, 0600
  assert(fd >= 0, 'Cannot write private Resolve mailbox')
  C.chmod(path .. '.tmp', 384)
  local offset = 0
  while offset < #data do
    local n = tonumber(C.write(fd, data:sub(offset+1), #data-offset))
    if n <= 0 then C.close(fd); error('Mailbox write failed') end
    offset = offset + n
  end
  C.close(fd); assert(C.rename(path .. '.tmp', path) == 0, 'Mailbox rename failed')
end
local function encode(x)
  local t = type(x)
  if x == null or t == 'nil' then return 'null' end
  if t == 'boolean' then return x and 'true' or 'false' end
  if t == 'number' then assert(x==x and math.abs(x)<math.huge); return tostring(x) end
  if t == 'string' then return '"' .. x:gsub('[%z\1-\31\\"]', function(c)
    local e = {['"']='\\"', ['\\']='\\\\', ['\n']='\\n', ['\r']='\\r', ['\t']='\\t'}
    return e[c] or string.format('\\u%04x', string.byte(c))
  end) .. '"' end
  assert(t == 'table', 'Unsupported result type')
  local array, n = true, 0
  for k in pairs(x) do n=n+1; if type(k)~='number' or k<1 or k%1~=0 then array=false end end
  local out = {}
  if array and n>0 and n==#x then
    for i=1,n do out[i]=encode(x[i]) end
    return '[' .. table.concat(out, ',') .. ']'
  end
  for k,v in pairs(x) do out[#out+1]=encode(tostring(k)) .. ':' .. encode(v) end
  return '{' .. table.concat(out, ',') .. '}'
end
local function decode(s)
  local i, value = 1
  local function white() local _,e=s:find('^[ \r\n\t]*',i); i=(e or i-1)+1 end
  local function str()
    assert(s:sub(i,i)=='"'); i=i+1; local out={}
    while i<=#s do
      local c=s:sub(i,i); i=i+1
      if c=='"' then return table.concat(out) end
      if c=='\\' then
        local e=s:sub(i,i); i=i+1
        local esc={['"']='"',['\\']='\\',['/']='/',b='\b',f='\f',n='\n',r='\r',t='\t'}
        if e=='u' then
          local h=s:sub(i,i+3); assert(h:match('^%x%x%x%x$')); local n=tonumber(h,16); i=i+4
          assert(n<128, 'Use UTF-8 rather than unicode escapes'); out[#out+1]=string.char(n)
        else assert(esc[e], 'Invalid JSON escape'); out[#out+1]=esc[e] end
      else assert(c:byte()>=32); out[#out+1]=c end
    end
    error('Unterminated string')
  end
  value=function(depth)
    assert(depth<40, 'Request too deep'); white(); local c=s:sub(i,i)
    if c=='"' then return str() end
    if c=='{' or c=='[' then
      local arr=c=='['; local close=arr and ']' or '}'; i=i+1; white(); local t={}
      if s:sub(i,i)==close then i=i+1; return t end
      while true do
        local k=arr and #t+1 or str(); white()
        if not arr then assert(s:sub(i,i)==':'); i=i+1 end
        t[k]=value(depth+1); white(); local e=s:sub(i,i); i=i+1
        if e==close then return t end
        assert(e==','); white()
      end
    end
    for _,v in ipairs({'true','false','null'}) do
      if s:sub(i,i+#v-1)==v then i=i+#v; if v=='null' then return null end; return v=='true' end
    end
    local num=s:match('^-?%d+%.?%d*[eE]?[+-]?%d*',i); assert(num and tonumber(num), 'Invalid JSON value')
    i=i+#num; return tonumber(num)
  end
  local result=value(0); white(); assert(i>#s, 'Trailing JSON'); return result
end
local methods = decode(__METHODS__)
local allowed = {}
for kind,names in pairs(methods) do allowed[kind]={}; for _,name in ipairs(names) do allowed[kind][name]=true end end
local objectKinds = {GetProjectManager='ProjectManager',GetCurrentProject='Project',GetMediaPool='MediaPool',
  GetCurrentTimeline='Timeline',CreateEmptyTimeline='Timeline',DuplicateTimeline='Timeline',GetTimelineByIndex='Timeline',GetMediaPoolItem='MediaPoolItem',ImportFusionComp='FusionComp',GetFusionCompByIndex='FusionComp',FindTool='FusionTool'}
local listKinds = {ImportMedia='MediaPoolItem',AppendToTimeline='TimelineItem',GetItemListInTrack='TimelineItem'}
local objects, counter, session = {}, 0, nil
local function reference(object, kind)
  if object == nil then return null end
  counter=counter+1; assert(counter<10000, 'Too many Resolve handles')
  local id=tostring(counter); objects[id]={object=object,kind=kind}
  return {['$ref']=id,['$kind']=kind}
end
local function unpackValue(x)
  if x==null then return nil end
  if type(x)~='table' then return x end
  if x['$ref'] then return assert(objects[x['$ref']], 'Expired Resolve handle').object end
  local t={}; for k,v in pairs(x) do t[k]=unpackValue(v) end; return t
end
local function dispatch(r)
  assert(type(r.session)=='string' and #r.session==32, 'Invalid session')
  if session~=r.session then session=r.session; counter=0; objects={resolve={object=resolve,kind='Resolve'}} end
  local obj=assert(objects[r.target], 'Unknown Resolve handle')
  assert(allowed[obj.kind] and allowed[obj.kind][r.method], 'Unsupported Resolve method')
  assert(type(r.args)=='table' and #r.args<10, 'Invalid arguments')
  if obj.kind=='FusionTool' and r.method=='SetInput' then
    assert(#r.args==2 and r.args[1]=='StyledText' and type(r.args[2])=='string' and #r.args[2]<=2000, 'Only bounded text changes are supported')
  end
  local result=obj.object[r.method](obj.object, unpack(unpackValue(r.args)))
  if objectKinds[r.method] then return reference(result,objectKinds[r.method]) end
  if listKinds[r.method] then
    if not result then return null end
    local out={}; for _,object in ipairs(result) do out[#out+1]=reference(object,listKinds[r.method]) end
    return out
  end
  return result==nil and null or result
end
local generation=tostring(bmd.createuuid())
local version=resolve:GetVersionString()
local seen, readyAt, lastId = {}, 0, nil
print('GenMedia Resolve bridge started. Leave this Console session running; run Stop connection from GenMedia Editor to stop it.')
while true do
  local now=clock()
  if math.floor(now)~=readyAt then
    writefile('ready.json',encode({generation=generation,version=version})); readyAt=math.floor(now)
    for id,expires in pairs(seen) do if id~=lastId and expires<now-60 then seen[id]=nil end end
  end
  if readfile('stop')==generation then break end
  local raw=readfile('request.json')
  if raw then
    local ok,r=pcall(decode,raw)
    if ok and type(r)=='table' and type(r.id)=='string' and #r.id==32 and not seen[r.id] then
      seen[r.id]=type(r.expires)=='number' and r.expires or now; lastId=r.id
      local response={id=r.id,generation=generation}
      if r.generation~=generation or type(r.expires)~='number' or r.expires<now then response.error='Expired Resolve request'
      else
        local success,result=pcall(dispatch,r)
        if success then response.result=result else response.error=tostring(result) end
      end
      local success,payload=pcall(encode,response)
      if not success then payload=encode({id=r.id,generation=generation,error='Resolve returned unsupported data'}) end
      writefile('response.json',payload)
    end
  end
  bmd.wait(.03)
end
writefile('ready.json',encode({stopped_generation=generation}))
print('GenMedia Resolve bridge stopped.')
