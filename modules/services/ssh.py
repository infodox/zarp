import util, os, socket
from threading import Thread
from service import Service
from time import sleep

try:
	from stubssh import SSHStub, SSHHandler
except:
	pass

#
# emulate a basic SSH service; store usernames/passwords but reject them all.
# Certs too.
#
class ssh(Service):
	def __init__(self):
		self.priv_key = None
		super(ssh,self).__init__('SSH Server')

	#
	# If we weren't given a private key, remove the temp we generated
	#
	def cleanup(self):
		if self.priv_key == './privkey.key':
			os.system('rm -f privkey.key')
	
	# dispatch as a thread; this is called from gui
	def initialize_bg(self):
		try:
			# try importing here so we can catch it right away
			import paramiko
		except ImportError:
			util.Error('Paramiko libraries required for this module.')
			return False

		while True:
			try:
				self.priv_key = raw_input('Enter private key path or [enter] to generate: ')
				if len(self.priv_key) < 2:
					self.priv_key = None
				else:
					# try reading the private key before starting
					tmp = paramiko.RSAKey.from_private_key_file(self.priv_key)
				break
			except IOError:
				util.Error('Error reading key.')
				continue
			except:
				pass
		
		util.Msg('Initializing SSH server...')
		thread = Thread(target=self.initialize)
		thread.start()
		return True
	
	# initialization
	def initialize(self):
		try:
			# try importing here so we can catch it right away
			import paramiko
		except ImportError:
			util.Error('Paramiko libraries required for this module.')
			return

		level = getattr(paramiko.common, 'CRITICAL')
		paramiko.common.logging.basicConfig(level=level)
		# if the user did not specify a key, generate one
		if self.priv_key is None:
			if not util.check_program('openssl'):
				util.Error('OpenSSL required to generate cert/key files.')
				return
			if not util.does_file_exist('./privkey.key'):
				util.debug('Generating RSA private key...')
				tmp = util.init_app('openssl genrsa -out privkey.key 2048', True)
				util.debug('privkey.key was generated.')
			self.priv_key = './privkey.key'

		try:
			server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
			server_socket.settimeout(3)
			server_socket.bind(('0.0.0.0', 22))
			server_socket.listen(1)
			self.running = True

			while self.running:
				try:
					con, addr = server_socket.accept()
				except KeyboardInterrupt:
					return
				except:
					# timeout
					continue
				pkey = paramiko.RSAKey.from_private_key_file(self.priv_key)
				transport = paramiko.Transport(con)
				transport.add_server_key(pkey)
				transport.set_subsystem_handler('handler', paramiko.SFTPServer, SSHHandler)

				context = { 'dump' : self.dump, 'log_data' : self.log_data,
							'log_file': self.log_file }
				server = SSHStub(context)
				try:
					transport.start_server(server=server)
					channel = transport.accept()
					while transport.is_active():
						sleep(1)
				except socket.error as j:
					if j.errno == 104:
					 	# just means we've got a broken pipe, or
						# the peer dropped unexpectedly
					 	continue
					else:
						raise Exception()
				except IOError:
					util.Error('There was an error reading the keyfile.')
					return False
				except EOFError:
					# thrown when we dont get the key correctly, or
					# remote host gets mad because the key changed
					continue
				except:
					raise Exception()
		except KeyboardInterrupt:
			pass
		except Exception as j:
			util.Error('Error with server: %s'%j)
		finally:
			self.running = False
			self.cleanup()
