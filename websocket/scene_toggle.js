const socketToken = 'd9a1a782725fb4aac142689b2263425f2d11a574'; //Socket token from /socket/token end point
  
//Connect to socket
const streamlabs = io(`https://sockets.streamlabs.com?token=${socketToken}`, {transports: ['websocket']});

//Perform Action on event
streamlabs.on('event', (eventData) => {
  if (!eventData.for && eventData.type === 'donation') {
    //code to handle donation events
    console.log(eventData.message);
  }
  if (eventData.for === 'twitch_account') {
    switch(eventData.type) {
      case 'follow':
        //code to handle follow events
        console.log(eventData.message);
        break;
      case 'subscription':
        //code to handle subscription events
        console.log(eventData.message);
        break;
      default:
        //default case
        console.log(eventData.message);

streamlabs.