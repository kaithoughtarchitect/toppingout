// Imported first by gaffer.test.ts. The tests run in one process (`npx tsx addons/gaffer/gaffer.test.ts`),
// not under `--test`, so Node's runner sets neither NODE_TEST_CONTEXT nor --test. Setting NODE_TEST
// here, before env.ts loads, keeps env.ts from reading a real .env and its API keys during the tests.
//
// Why not `--test`: under it, Node 22 runs the file in a child process and reads the child's stdout for
// its report frames. That parser can crash on ordinary output ("Unable to deserialize cloned data due to
// invalid or unsupported version", nodejs/node#66164), which failed CI at random in test 18. The fix
// (nodejs/node#66273) is in Node's main branch, not in Node 22.
process.env.NODE_TEST ||= "1";
