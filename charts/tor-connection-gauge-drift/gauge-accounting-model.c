/* Isolated accounting model: Tor 0.4.8.16 functions copied verbatim.
 * Caller schedule is synthetic; this is not a Tor binary/network experiment.
 * Forty thousand simulated normally counted open connections.
 */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/socket.h>
#define tor_assert assert
#define CONN_TYPE_MAX_ 64
#define CONN_DIRECTION_INITIATED 0
#define CONN_DIRECTION_RECEIVED 1
#define CONN_DIRECTION(from_listener) ((from_listener) ? CONN_DIRECTION_RECEIVED : CONN_DIRECTION_INITIATED)
static uint64_t conn_num_created_v4[2][CONN_TYPE_MAX_];
static uint64_t conn_num_created_v6[2][CONN_TYPE_MAX_];
static uint64_t conn_num_opened_v4[2][CONN_TYPE_MAX_];
static uint64_t conn_num_opened_v6[2][CONN_TYPE_MAX_];
void
rep_hist_note_conn_opened(bool from_listener, unsigned int type, int af)
{
  tor_assert(type <= CONN_TYPE_MAX_);

  unsigned int dir = CONN_DIRECTION(from_listener);

  switch (af) {
  case AF_INET:
    conn_num_created_v4[dir][type]++;
    conn_num_opened_v4[dir][type]++;
    break;
  case AF_INET6:
    conn_num_created_v6[dir][type]++;
    conn_num_opened_v6[dir][type]++;
    break;
  default:
    /* Ignore non IP connections at this point in time. */
    break;
  }
}

void
rep_hist_note_conn_closed(bool from_listener, unsigned int type, int af)
{
  tor_assert(type <= CONN_TYPE_MAX_);

  unsigned int dir = CONN_DIRECTION(from_listener);

  switch (af) {
  case AF_INET:
    if (conn_num_opened_v4[dir][type] > 0) {
      conn_num_opened_v4[dir][type]--;
    }
    break;
  case AF_INET6:
    if (conn_num_opened_v6[dir][type] > 0) {
      conn_num_opened_v6[dir][type]--;
    }
    break;
  default:
    /* Ignore non IP connections at this point in time. */
    break;
  }
}

uint64_t
rep_hist_get_conn_opened(bool from_listener, unsigned int type, int af)
{
  tor_assert(type <= CONN_TYPE_MAX_);
  unsigned int dir = CONN_DIRECTION(from_listener);
  switch (af) {
  case AF_INET:
    return conn_num_opened_v4[dir][type];
  case AF_INET6:
    return conn_num_opened_v6[dir][type];
  default:
    return 0;
  }
}
int main(void) {
 const unsigned type=1;
 for (int i=0;i<40000;i++) rep_hist_note_conn_opened(true,type,AF_INET);
 puts("unmatched_closes,simulated_open_connections,exported_gauge");
 for (int i=0;i<=50000;i++) {
   if(i%100==0) printf("%d,40000,%llu\n",i,(unsigned long long)rep_hist_get_conn_opened(true,type,AF_INET));
   rep_hist_note_conn_closed(true,type,AF_INET);
 }
 assert(rep_hist_get_conn_opened(true,type,AF_INET)==0);
 return 0;
}
